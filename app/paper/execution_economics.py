"""Conservative PAPER fills from exact-size fork evidence, never guessed costs.

The fork measures the baseline (including pool fee, impact and transfer loss).
PAPER consumes the empirical minOut headroom once as a worst-case reserve for
natural drift OR sandwich loss. This is a PAPER policy, not observed MEV, an
expected loss, or proof of protection for the fork's zero-minOut transaction.
"""
import math
from decimal import Decimal

from app.config.contracts import USDT
from app.risk.execution_envelope import build_minout_envelope, empirical_quote_drift


def _integer(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not execution evidence")
    number = int(value, 16) if isinstance(value, str) and value.startswith("0x") else int(value)
    if not isinstance(value, str) and number != value:
        raise ValueError("nonintegral execution evidence")
    return number


def paper_execution_fill(*, side, execution, context, amount_in_raw,
                         known_edge_fraction=None):
    result = {
        "state": "UNKNOWN", "reason": "EXECUTION_COST_EVIDENCE_UNAVAILABLE",
        "accounting_semantics": "CONSERVATIVE_PAPER_MINOUT_BOUND",
        "bound_scope": "PAPER_POLICY_ONLY", "fork_minout_enforced": False,
        "mev_expected_loss_usd": None,
        "mev_and_natural_drift_are_additive": False,
        "gas_usd": None, "output_floor_amount": None,
        "net_proceeds_usdt": None,
    }
    try:
        if side not in {"BUY", "SELL"} or execution.get("status") != "SUCCESS":
            return result
        block = _integer(execution["block"]["number"])
        if (block != _integer(context["runtime_price_latest_block"])
                or _integer(execution["block"]["chain_id"]) != 56
                or str(context["quote_token"]).lower() != USDT.lower()
                or str(execution["quote_token"]).lower() != USDT.lower()):
            return result
        token_decimals, quote_decimals = context["token_decimals"], context["quote_decimals"]
        if any(type(d) is not int or not 0 <= d <= 255 for d in (token_decimals, quote_decimals)):
            return result
        raw = execution["raw"]
        amount = _integer(amount_in_raw)
        seed_key = "seed_quote_raw" if side == "BUY" else "seed_token_raw"
        if amount <= 0 or _integer(raw["transaction"][seed_key]) != amount:
            return result
        received = _integer(execution["received_token_raw" if side == "BUY" else "received_quote_raw"])
        if received <= 0 or received != _integer(execution["recipient_balance_delta_raw"]):
            return result

        # Missing approval evidence differs from an explicitly unnecessary approval.
        if raw["receipt"] is None:
            return result
        gas_wei = 0
        for receipt in (raw["receipt"], raw["approval_receipt"]):
            if receipt is None:
                continue
            if _integer(receipt["status"]) != 1:
                return result
            units, price = _integer(receipt["gasUsed"]), _integer(receipt["effectiveGasPrice"])
            if units <= 0 or price < 0:
                return result
            gas_wei += units * price
        native_usd = float(context["wbnb_usd_estimate"])
        if not math.isfinite(native_usd) or native_usd <= 0:
            return result
        gas = gas_wei / 1e18 * native_usd
        result["gas_usd"] = gas

        samples = context["reserve_samples"]
        blocks = [_integer(sample["block"]) for sample in samples]
        if (len(blocks) < 2 or blocks != sorted(set(blocks)) or blocks[-1] != block
                or context["implied_v2_fee_state"] != "READY"):
            result.update(state="UNBOUNDED", reason="QUOTE_HISTORY_NOT_PROVEN")
            return result
        spot = float(samples[-1]["quote_reserve"]) / float(samples[-1]["token_reserve"])
        input_decimals = quote_decimals if side == "BUY" else token_decimals
        output_decimals = token_decimals if side == "BUY" else quote_decimals
        output = received / 10 ** output_decimals
        baseline_usd = output * spot if side == "BUY" else output
        drift = empirical_quote_drift(
            reserve_samples=samples, amount_in=amount / 10 ** input_decimals,
            fee_fraction=context["implied_v2_fee_fraction"], side=side,
        )
        envelope = build_minout_envelope(
            baseline_executable_output_usd=baseline_usd,
            quote_drift_fraction=drift.get("worst_adverse_drift_fraction"),
            edge_budget_fraction=known_edge_fraction,
        )
        result.update(state=envelope["state"], reason=envelope["reason"], envelope=envelope)
        if envelope["state"] != "BOUNDED":
            return result
        # Round down to an executable raw amount. The reserve already covers MEV.
        floor_raw = int(Decimal(received) * Decimal(str(envelope["min_out_fraction"])))
        floor = floor_raw / 10 ** output_decimals
        if floor <= 0 or not all(math.isfinite(v) for v in (output, floor, gas, baseline_usd)):
            result.update(state="UNKNOWN", reason="INVALID_EXECUTION_AMOUNTS")
            return result
        result.update(
            block_number=block, amount_in_raw=amount, baseline_output_amount=output,
            output_floor_raw=floor_raw, output_floor_amount=floor,
            adverse_execution_reserve_usd=(output - floor) * (spot if side == "BUY" else 1.0),
            net_proceeds_usdt=floor - gas if side == "SELL" else None,
        )
        return result
    except (KeyError, TypeError, ValueError, OverflowError, ArithmeticError):
        result.update(state="UNKNOWN", reason="EXECUTION_COST_EVIDENCE_UNAVAILABLE",
                      output_floor_amount=None, net_proceeds_usdt=None)
        return result
