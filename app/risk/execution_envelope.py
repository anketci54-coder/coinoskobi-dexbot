from __future__ import annotations

import math

from app.dex.price_impact import constant_product_quote


def _finite_positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value) or value <= 0:
        return None

    return value


def _fee(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value) or not 0.0 <= value < 1.0:
        return None

    return value


def empirical_quote_drift(
    *,
    reserve_samples,
    amount_in,
    fee_fraction,
    side,
):
    """
    Replay one exact trade size across recent V2 reserve samples.

    Returns the worst observed adverse output drawdown as a fraction.
    No percentile, volatility multiplier or fixed tolerance is invented.
    """
    amount = _finite_positive(amount_in)
    fee = _fee(fee_fraction)
    direction = str(side or "").strip().upper()

    if (
        amount is None
        or fee is None
        or direction not in {"BUY", "SELL"}
    ):
        return {
            "state": "UNKNOWN",
            "reason": "INVALID_QUOTE_INPUT",
            "quotes": [],
            "current_quote_out": None,
            "worst_adverse_drift_fraction": None,
            "sample_count": 0,
            "decision_authority": False,
            "execution_authority": False,
        }

    quotes = []

    for sample in reserve_samples or ():
        if not isinstance(sample, dict):
            continue

        token_reserve = _finite_positive(
            sample.get("token_reserve")
        )
        quote_reserve = _finite_positive(
            sample.get("quote_reserve")
        )

        if token_reserve is None or quote_reserve is None:
            continue

        if direction == "BUY":
            reserve_in = quote_reserve
            reserve_out = token_reserve
        else:
            reserve_in = token_reserve
            reserve_out = quote_reserve

        quote = constant_product_quote(
            reserve_in=reserve_in,
            reserve_out=reserve_out,
            amount_in=amount,
            fee_fraction=fee,
        )

        if quote.get("state") != "READY":
            continue

        output = _finite_positive(
            quote.get("amount_out")
        )
        if output is None:
            continue

        quotes.append({
            "block": sample.get("block"),
            "amount_out": output,
        })

    if len(quotes) < 2:
        return {
            "state": "UNKNOWN",
            "reason": "QUOTE_HISTORY_INSUFFICIENT",
            "quotes": quotes,
            "current_quote_out": (
                quotes[-1]["amount_out"]
                if quotes
                else None
            ),
            "worst_adverse_drift_fraction": None,
            "sample_count": len(quotes),
            "decision_authority": False,
            "execution_authority": False,
        }

    running_peak = quotes[0]["amount_out"]
    worst_drawdown = 0.0

    for item in quotes:
        output = item["amount_out"]
        running_peak = max(
            running_peak,
            output,
        )
        if running_peak > 0:
            worst_drawdown = max(
                worst_drawdown,
                1.0 - output / running_peak,
            )

    return {
        "state": "READY",
        "reason": "EMPIRICAL_EXACT_SIZE_QUOTE_DRIFT",
        "quotes": quotes,
        "current_quote_out": quotes[-1]["amount_out"],
        "worst_adverse_drift_fraction": worst_drawdown,
        "sample_count": len(quotes),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def derive_buy_execution_economics(
    *,
    buy_evidence,
    exit_evidence,
    entry_amount_usdt,
    known_edge_fraction=None,
):
    """
    Derive BUY-side execution economics from the pinned fork receipt/balance
    delta plus the same-block reserve evidence.

    No provider tax metadata is required. The difference between the exact V2
    route quote and the simulated recipient balance delta is observed transfer
    retention. Gas comes from the simulated receipt and is monetized only when
    the pinned WBNB/USD estimate is available.
    """
    buy = (
        buy_evidence.get("buy")
        if isinstance(buy_evidence, dict)
        and isinstance(
            buy_evidence.get("buy"),
            dict,
        )
        else buy_evidence
        if isinstance(buy_evidence, dict)
        else {}
    )
    exit_data = (
        exit_evidence
        if isinstance(exit_evidence, dict)
        else {}
    )

    amount = _finite_positive(
        entry_amount_usdt
    )
    status = str(
        buy.get("status")
        or "UNKNOWN"
    ).upper()
    block = (
        buy.get("block")
        if isinstance(
            buy.get("block"),
            dict,
        )
        else {}
    )

    try:
        block_number = int(
            block.get("number")
        )
    except (TypeError, ValueError):
        block_number = None

    try:
        evidence_block = int(
            exit_data.get(
                "runtime_price_latest_block"
            )
        )
    except (TypeError, ValueError):
        evidence_block = None

    token_decimals = exit_data.get(
        "token_decimals"
    )
    fee_state = str(
        exit_data.get(
            "implied_v2_fee_state"
        )
        or "UNKNOWN"
    ).upper()
    fee = _fee(
        exit_data.get(
            "implied_v2_fee_fraction"
        )
    )
    samples = exit_data.get(
        "reserve_samples"
    )

    base = {
        "state": "UNKNOWN",
        "reason": None,
        "block_number": block_number,
        "evidence_block_number": evidence_block,
        "block_match": (
            block_number is not None
            and evidence_block is not None
            and block_number == evidence_block
        ),
        "entry_amount_usdt": amount,
        "theoretical_route_token_out": None,
        "actual_received_token": None,
        "buy_transfer_retention": None,
        "buy_transfer_loss_fraction": None,
        "gas_used": buy.get("gas_used"),
        "effective_gas_price": buy.get(
            "effective_gas_price"
        ),
        "buy_gas_usd": None,
        "baseline_executable_output_usd": None,
        "deterministic_buy_shortfall_usd": None,
        "quote_drift_fraction": None,
        "slippage_tolerance_pct": None,
        "min_out_fraction": None,
        "total_adverse_execution_reserve_usd": None,
        "mev_upper_bound_usd": None,
        "mev_and_natural_drift_are_additive": False,
        "authority": False,
    }

    if status != "SUCCESS":
        base["reason"] = "BUY_EXECUTION_NOT_PROVEN"
        return base

    if (
        amount is None
        or block_number is None
        or evidence_block is None
        or block_number != evidence_block
    ):
        base["reason"] = "PINNED_BLOCK_MISMATCH_OR_AMOUNT_UNKNOWN"
        return base

    if (
        type(token_decimals) is not int
        or not 0 <= token_decimals <= 255
    ):
        base["reason"] = "TOKEN_DECIMALS_UNAVAILABLE"
        return base

    if (
        fee_state != "READY"
        or fee is None
    ):
        base["reason"] = "VERIFIED_V2_FEE_UNAVAILABLE"
        return base

    if not isinstance(samples, (list, tuple)):
        base["reason"] = "RESERVE_SAMPLES_UNAVAILABLE"
        return base

    current = None
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        try:
            sample_block = int(
                sample.get("block")
            )
        except (TypeError, ValueError):
            continue
        if sample_block == block_number:
            current = sample

    if current is None:
        base["reason"] = "PINNED_RESERVE_SAMPLE_UNAVAILABLE"
        return base

    token_reserve = _finite_positive(
        current.get("token_reserve")
    )
    quote_reserve = _finite_positive(
        current.get("quote_reserve")
    )
    if token_reserve is None or quote_reserve is None:
        base["reason"] = "PINNED_RESERVES_INVALID"
        return base

    route_quote = constant_product_quote(
        reserve_in=quote_reserve,
        reserve_out=token_reserve,
        amount_in=amount,
        fee_fraction=fee,
    )
    theoretical = _finite_positive(
        route_quote.get("amount_out")
    )
    try:
        received_raw = int(
            buy.get("received_token_raw")
        )
    except (TypeError, ValueError):
        received_raw = 0
    actual = (
        received_raw
        / (10 ** token_decimals)
        if received_raw > 0
        else None
    )

    if theoretical is None or actual is None:
        base["reason"] = "BUY_BALANCE_DELTA_OR_ROUTE_QUOTE_UNAVAILABLE"
        return base

    retention = actual / theoretical
    if (
        not math.isfinite(retention)
        or retention <= 0
        or retention > 1.000001
    ):
        base["reason"] = "NON_STANDARD_BUY_TRANSFER_DELTA"
        return base

    retention = min(1.0, retention)
    transfer_loss = 1.0 - retention

    spot_price_usd = (
        quote_reserve
        / token_reserve
    )
    baseline_output_usd = (
        actual
        * spot_price_usd
    )

    gas_wei = buy.get(
        "execution_gas_cost_wei"
    )
    wbnb_usd = _finite_positive(
        exit_data.get(
            "wbnb_usd_estimate"
        )
    )
    try:
        gas_wei = int(gas_wei)
    except (TypeError, ValueError):
        gas_wei = None

    buy_gas_usd = (
        gas_wei / 1e18 * wbnb_usd
        if (
            gas_wei is not None
            and gas_wei >= 0
            and wbnb_usd is not None
        )
        else None
    )

    drift = empirical_quote_drift(
        reserve_samples=samples,
        amount_in=amount,
        fee_fraction=fee,
        side="BUY",
    )
    drift_fraction = (
        drift.get(
            "worst_adverse_drift_fraction"
        )
        if drift.get("state") == "READY"
        else None
    )

    edge_budget = None
    if known_edge_fraction is not None:
        try:
            edge_budget = float(
                known_edge_fraction
            )
        except (TypeError, ValueError):
            edge_budget = None
        if (
            edge_budget is None
            or not math.isfinite(edge_budget)
            or edge_budget < 0
        ):
            edge_budget = None

    envelope = build_minout_envelope(
        baseline_executable_output_usd=(
            baseline_output_usd
        ),
        quote_drift_fraction=(
            drift_fraction
        ),
        edge_budget_fraction=(
            edge_budget
        ),
    )

    base.update({
        "state": (
            "READY"
            if envelope.get("state") == "BOUNDED"
            else envelope.get("state")
        ),
        "reason": envelope.get("reason"),
        "theoretical_route_token_out": theoretical,
        "actual_received_token": actual,
        "buy_transfer_retention": retention,
        "buy_transfer_loss_fraction": transfer_loss,
        "buy_gas_usd": buy_gas_usd,
        "baseline_executable_output_usd": (
            baseline_output_usd
        ),
        "deterministic_buy_shortfall_usd": (
            max(
                0.0,
                amount
                - baseline_output_usd,
            )
        ),
        "quote_drift_fraction": drift_fraction,
        "slippage_tolerance_pct": (
            envelope.get(
                "slippage_tolerance_pct"
            )
        ),
        "min_out_fraction": (
            envelope.get(
                "min_out_fraction"
            )
        ),
        "total_adverse_execution_reserve_usd": (
            envelope.get(
                "adverse_execution_reserve_usd"
            )
        ),
        "mev_upper_bound_usd": (
            envelope.get(
                "adverse_execution_reserve_usd"
            )
        ),
    })

    return base


def build_minout_envelope(
    *,
    baseline_executable_output_usd,
    quote_drift_fraction,
    edge_budget_fraction=None,
):
    """
    Convert measured quote drift into the smallest evidence-backed minOut
    headroom. The headroom is also the total adverse-execution reserve.

    If an economic edge budget is supplied and cannot cover the measured
    drift, the envelope fails closed instead of widening slippage.
    """
    baseline = _finite_positive(
        baseline_executable_output_usd
    )

    try:
        drift = float(quote_drift_fraction)
    except (TypeError, ValueError):
        drift = None

    if (
        baseline is None
        or drift is None
        or not math.isfinite(drift)
        or not 0.0 <= drift < 1.0
    ):
        return {
            "state": "UNBOUNDED",
            "reason": "EXECUTION_HEADROOM_EVIDENCE_UNAVAILABLE",
            "slippage_tolerance_fraction": None,
            "slippage_tolerance_pct": None,
            "min_out_fraction": None,
            "adverse_execution_reserve_usd": None,
            "decision_authority": False,
            "execution_authority": False,
        }

    budget = None
    if edge_budget_fraction is not None:
        try:
            budget = float(edge_budget_fraction)
        except (TypeError, ValueError):
            budget = None

        if (
            budget is None
            or not math.isfinite(budget)
            or budget < 0
        ):
            return {
                "state": "UNBOUNDED",
                "reason": "EDGE_BUDGET_INVALID",
                "slippage_tolerance_fraction": None,
                "slippage_tolerance_pct": None,
                "min_out_fraction": None,
                "adverse_execution_reserve_usd": None,
                "decision_authority": False,
                "execution_authority": False,
            }

        if drift > budget:
            return {
                "state": "EDGE_BUDGET_EXCEEDED",
                "reason": "MEASURED_DRIFT_EXCEEDS_EXECUTION_EDGE_BUDGET",
                "slippage_tolerance_fraction": drift,
                "slippage_tolerance_pct": drift * 100.0,
                "min_out_fraction": 1.0 - drift,
                "adverse_execution_reserve_usd": baseline * drift,
                "edge_budget_fraction": budget,
                "decision_authority": False,
                "execution_authority": False,
            }

    return {
        "state": "BOUNDED",
        "reason": "EMPIRICAL_MINOUT_HEADROOM",
        "baseline_executable_output_usd": baseline,
        "slippage_tolerance_fraction": drift,
        "slippage_tolerance_pct": drift * 100.0,
        "min_out_fraction": 1.0 - drift,
        "adverse_execution_reserve_usd": baseline * drift,
        "edge_budget_fraction": budget,
        "double_count_guard": (
            "HEADROOM_IS_TOTAL_ADVERSE_EXECUTION_RESERVE"
        ),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
