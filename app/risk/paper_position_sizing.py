import json
import math
import sqlite3
import statistics
from pathlib import Path


PAPER_CAPITAL_USDT = 10_000.0


def _number(value):
    try:
        if value is None:
            return None
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def _positive(value):
    value = _number(value)
    if value is None or value <= 0:
        return None
    return value


def _json_dict(raw):
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}

    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    return value if isinstance(value, dict) else {}


def _find_number(node, names):
    if isinstance(node, dict):
        for key in names:
            if key in node:
                value = _number(node.get(key))
                if value is not None:
                    return value

        for value in node.values():
            found = _find_number(value, names)
            if found is not None:
                return found

    elif isinstance(node, (list, tuple)):
        for value in node:
            found = _find_number(value, names)
            if found is not None:
                return found

    return None


def paper_available_capital_usdt(
    conn,
    starting_capital_usdt=PAPER_CAPITAL_USDT,
):
    """Durable free-cash truth for PAPER_10K_V2."""
    starting = _number(starting_capital_usdt)
    if starting is None or starting < 0:
        starting = 0.0

    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(
                CASE
                WHEN UPPER(COALESCE(status, ''))='CLOSED'
                THEN COALESCE(net_pnl_usdt, net_pnl, 0)
                ELSE 0
                END
            ), 0),
            COALESCE(SUM(
                CASE
                WHEN UPPER(COALESCE(status, ''))='OPEN'
                THEN COALESCE(realized_pnl_usdt, 0)
                ELSE 0
                END
            ), 0),
            COALESCE(SUM(
                CASE
                WHEN UPPER(COALESCE(status, ''))='OPEN'
                THEN COALESCE(
                    remaining_cost_basis_usdt,
                    entry_amount_usdt,
                    0
                )
                ELSE 0
                END
            ), 0)
        FROM paper_trades
        WHERE paper_account_version='PAPER_10K_V2'
        """
    ).fetchone()

    if row is None:
        return max(0.0, starting)

    closed_pnl = _number(row[0]) or 0.0
    open_realized_pnl = _number(row[1]) or 0.0
    open_remaining_basis = _number(row[2]) or 0.0

    return max(
        0.0,
        starting
        + closed_pnl
        + open_realized_pnl
        - open_remaining_basis,
    )


def _calibration_empty(reason):
    return {
        "ready": False,
        "reason": reason,
        "gap_multiplier": None,
        "gap_median": None,
        "gap_statistic": None,
        "cost_uncertainty_fraction": None,
        "account_risk_budget_usdt": None,
        "account_risk_statistic": None,
        "gap_samples": 0,
        "cost_samples": 0,
        "account_risk_samples": 0,
    }


def _table_columns(db, table_name):
    return {
        row[1]
        for row in db.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }


def _column_expr(columns, name):
    return name if name in columns else "NULL"


def _closed_outcome_rows(db, table_name):
    exists = db.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    ).fetchone()

    if exists is None:
        return []

    columns = _table_columns(db, table_name)

    required = {
        "status",
        "entry_price",
        "entry_amount_usdt",
        "mathematical_plan_json",
        "math_state_json",
    }

    if not required.issubset(columns):
        return []

    names = (
        "current_price",
        "exit_price",
        "net_pnl",
        "gross_pnl_usdt",
        "net_pnl_usdt",
    )

    expressions = {
        name: _column_expr(columns, name)
        for name in names
    }

    return db.execute(
        f"""
        SELECT
            entry_price,
            entry_amount_usdt,
            mathematical_plan_json,
            math_state_json,
            {expressions['current_price']} AS current_price,
            {expressions['exit_price']} AS exit_price,
            {expressions['net_pnl']} AS net_pnl,
            {expressions['gross_pnl_usdt']} AS gross_pnl_usdt,
            {expressions['net_pnl_usdt']} AS net_pnl_usdt
        FROM {table_name}
        WHERE UPPER(COALESCE(status, ''))='CLOSED'
          AND mathematical_plan_json IS NOT NULL
        """
    ).fetchall()


def _planned_loss_fraction(row):
    entry = _positive(row["entry_price"])
    if entry is None:
        return None

    plan = _json_dict(row["mathematical_plan_json"])
    state = _json_dict(row["math_state_json"])

    stop = _positive(state.get("last_stop"))

    if stop is None:
        entry_plan = (
            plan.get("entry")
            if isinstance(plan.get("entry"), dict)
            else {}
        )
        stop = _positive(entry_plan.get("band_low"))

    if stop is None or stop >= entry:
        return None

    fraction = 1.0 - stop / entry
    return fraction if fraction > 0 else None


def _observed_market_loss_fraction(row):
    """
    Closed-outcome downside truth.

    Preference order:
    1. closed gross PnL over original entry amount;
    2. explicit exit price;
    3. legacy current price;
    4. closed net PnL as a final compatibility fallback.

    This deliberately avoids treating a stale current_price field as
    canonical when durable closed accounting or exit price is present.
    """
    amount = _positive(row["entry_amount_usdt"])
    entry = _positive(row["entry_price"])

    if amount is None:
        return None

    gross = _number(row["gross_pnl_usdt"])
    if gross is not None and gross < 0:
        return min(1.0, max(0.0, -gross / amount))

    if entry is not None:
        exit_price = _positive(row["exit_price"])
        if exit_price is not None:
            return min(
                1.0,
                max(0.0, 1.0 - exit_price / entry),
            )

        current = _positive(row["current_price"])
        if current is not None:
            return min(
                1.0,
                max(0.0, 1.0 - current / entry),
            )

    net = _number(row["net_pnl_usdt"])
    if net is None:
        net = _number(row["net_pnl"])

    if net is not None and net < 0:
        return min(1.0, max(0.0, -net / amount))

    return 0.0


def _observed_cost_fraction(row):
    amount = _positive(row["entry_amount_usdt"])
    if amount is None:
        return None

    gross = _number(row["gross_pnl_usdt"])
    net_usdt = _number(row["net_pnl_usdt"])

    if gross is not None and net_usdt is not None:
        value = max(0.0, (gross - net_usdt) / amount)
        return value if math.isfinite(value) else None

    net = _number(row["net_pnl"])
    entry = _positive(row["entry_price"])

    mark = _positive(row["exit_price"])
    if mark is None:
        mark = _positive(row["current_price"])

    if (
        net is not None
        and entry is not None
        and mark is not None
    ):
        mark_pnl = amount * (mark / entry - 1.0)
        value = max(0.0, (mark_pnl - net) / amount)
        return value if math.isfinite(value) else None

    return None


def _observed_account_loss_usdt(row):
    net = _number(row["net_pnl_usdt"])
    if net is None:
        net = _number(row["net_pnl"])

    if net is None or net >= 0:
        return None

    loss = -net
    return loss if math.isfinite(loss) and loss > 0 else None


def _empirical_outcome_calibration(
    db_path="data/paper_trades.db",
):
    """
    Learn gap overshoot, cost uncertainty, and realized account-loss
    budget from durable closed paper outcomes only. No fixed risk
    percentage is introduced.
    """
    path = Path(db_path)
    if not path.exists():
        return _calibration_empty("OUTCOME_DB_MISSING")

    try:
        db = sqlite3.connect(
            f"file:{path}?mode=ro",
            uri=True,
        )
        db.row_factory = sqlite3.Row

        active_exists = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name='paper_trades'
            """
        ).fetchone()

        if active_exists is None:
            db.close()
            return _calibration_empty("PAPER_TRADES_MISSING")

        active_columns = _table_columns(db, "paper_trades")
        minimum = {
            "status",
            "entry_price",
            "entry_amount_usdt",
            "mathematical_plan_json",
            "math_state_json",
        }

        if not minimum.issubset(active_columns):
            db.close()
            return _calibration_empty("OUTCOME_COLUMNS_INCOMPLETE")

        rows = []
        for table_name in (
            "paper_trades_archive",
            "paper_trades",
        ):
            rows.extend(
                _closed_outcome_rows(db, table_name)
            )

        db.close()

    except sqlite3.Error:
        return _calibration_empty("OUTCOME_DB_READ_FAILED")

    gap_ratios = []
    cost_residuals = []
    account_losses = []

    for row in rows:
        planned_loss = _planned_loss_fraction(row)
        observed_loss = _observed_market_loss_fraction(row)
        cost_fraction = _observed_cost_fraction(row)
        account_loss = _observed_account_loss_usdt(row)

        if (
            account_loss is not None
            and math.isfinite(account_loss)
        ):
            account_losses.append(account_loss)

        if (
            cost_fraction is not None
            and math.isfinite(cost_fraction)
        ):
            cost_residuals.append(cost_fraction)

        if (
            planned_loss is None
            or observed_loss is None
            or planned_loss <= 0
            or observed_loss <= 0
        ):
            continue

        ratio = observed_loss / planned_loss

        if math.isfinite(ratio) and ratio > 0:
            gap_ratios.append(ratio)

    gap_median = (
        statistics.median(gap_ratios)
        if gap_ratios
        else None
    )

    gap_multiplier = max(gap_ratios) if gap_ratios else None

    positive_costs = [
        value
        for value in cost_residuals
        if value > 0
    ]

    cost_uncertainty = (
        statistics.median(positive_costs)
        if positive_costs
        else None
    )

    account_risk_budget = (
        statistics.median(account_losses)
        if account_losses
        else None
    )

    ready = (
        gap_multiplier is not None
        and gap_multiplier > 0
        and account_risk_budget is not None
        and account_risk_budget > 0
    )

    return {
        "ready": ready,
        "reason": (
            "EMPIRICAL_OUTCOME_CALIBRATION"
            if ready
            else "EMPIRICAL_RISK_BUDGET_UNOBSERVED"
        ),
        "gap_multiplier": gap_multiplier,
        "gap_median": gap_median,
        "gap_statistic": "MAX_OBSERVED" if gap_multiplier else None,
        "cost_uncertainty_fraction": cost_uncertainty,
        "account_risk_budget_usdt": account_risk_budget,
        "account_risk_statistic": (
            "MEDIAN_REALIZED_LOSS_USDT"
            if account_risk_budget is not None
            else None
        ),
        "gap_samples": len(gap_ratios),
        "cost_samples": len(positive_costs),
        "account_risk_samples": len(account_losses),
    }


def _zero_result(
    *,
    available,
    raw_amount,
    safe_quote_reserve,
    risk_log_distance,
    gap_multiplier,
    calibration,
    empirical_cost_uncertainty,
    effective_edge,
    cost_complete,
    blockers,
):
    return {
        "entry_amount_usdt": 0.0,
        "risk_amount_usdt": 0.0,
        "capital_before_usdt": available,
        "capital_after_entry_usdt": available,
        "position_size_pct": 0.0,
        "sizing_reason": "MATHEMATICAL_POSITION_SIZE_ZERO",
        "formula_authority": "DATA_DERIVED",
        "magic_percentage_rule": False,
        "sizing_model": "EMPIRICAL_GAP_EXIT_CAPACITY_V2",
        "blockers": sorted(set(blockers)),
        "raw_plan_amount_usdt": raw_amount,
        "safe_quote_reserve_usd": safe_quote_reserve,
        "risk_log_distance": risk_log_distance,
        "gap_multiplier": gap_multiplier,
        "gap_samples": calibration.get("gap_samples"),
        "empirical_cost_uncertainty_fraction": (
            empirical_cost_uncertainty
        ),
        "cost_samples": calibration.get("cost_samples"),
        "account_risk_budget_usdt": calibration.get(
            "account_risk_budget_usdt"
        ),
        "account_risk_statistic": calibration.get(
            "account_risk_statistic"
        ),
        "account_risk_samples": calibration.get(
            "account_risk_samples"
        ),
        "effective_edge_fraction": effective_edge,
        "cost_complete": cost_complete,
        "kelly_diagnostic_only": True,
    }


def calculate_paper_position_size(
    *,
    mathematical_plan=None,
    available_capital_usdt=None,
    db_path="data/paper_trades.db",
    **_legacy,
):
    """Risk-first position sizing with empirical tail-gap calibration."""
    plan = (
        mathematical_plan
        if isinstance(mathematical_plan, dict)
        else {}
    )

    capital = (
        plan.get("capital")
        if isinstance(plan.get("capital"), dict)
        else {}
    )

    expected = (
        plan.get("expected")
        if isinstance(plan.get("expected"), dict)
        else {}
    )

    cost_model = (
        plan.get("cost_model")
        if isinstance(plan.get("cost_model"), dict)
        else {}
    )

    raw_amount = max(
        0.0,
        _number(capital.get("entry_amount_usdt")) or 0.0,
    )

    available = max(
        0.0,
        _number(
            available_capital_usdt
            if available_capital_usdt is not None
            else capital.get("available_usdt")
        )
        or 0.0,
    )

    safe_quote_reserve = _positive(
        capital.get("safe_quote_reserve_usd")
    )

    liquidity_capacity_source = str(
        capital.get("liquidity_capacity_source")
        or ""
    ).strip().upper()

    risk_log_distance = _positive(
        _find_number(
            plan,
            {
                "risk_log_distance",
                "empirical_risk_log_distance",
            },
        )
    )

    full_edge = _number(
        expected.get("full_net_edge_fraction")
    )
    known_edge = _number(
        expected.get("known_net_edge_fraction")
    )
    cost_complete = bool(cost_model.get("cost_complete"))

    calibration = _empirical_outcome_calibration(
        db_path=db_path
    )
    gap_multiplier = _positive(
        calibration.get("gap_multiplier")
    )
    empirical_cost_uncertainty = _number(
        calibration.get("cost_uncertainty_fraction")
    )
    account_risk_budget = _positive(
        calibration.get("account_risk_budget_usdt")
    )

    blockers = []

    if liquidity_capacity_source == "EMPIRICAL_RESERVE_FLOOR":
        blockers.append(
            "LP_WITHDRAWAL_PROTECTION_UNVERIFIED"
        )

    if raw_amount <= 0:
        blockers.append("PLAN_AMOUNT_ZERO")
    if available <= 0:
        blockers.append("AVAILABLE_CAPITAL_ZERO")
    if safe_quote_reserve is None:
        blockers.append("EXIT_CAPACITY_UNKNOWN")
    if risk_log_distance is None:
        blockers.append("EMPIRICAL_RISK_DISTANCE_UNKNOWN")
    if gap_multiplier is None:
        blockers.append("GAP_RISK_UNOBSERVED")
    if account_risk_budget is None:
        blockers.append("ACCOUNT_RISK_BUDGET_UNOBSERVED")

    if cost_complete:
        effective_edge = full_edge
        if effective_edge is None:
            blockers.append("FULL_NET_EDGE_UNKNOWN")
    else:
        if (
            known_edge is None
            or empirical_cost_uncertainty is None
        ):
            effective_edge = None
            blockers.append("COST_UNCERTAINTY_UNOBSERVED")
        else:
            effective_edge = known_edge - empirical_cost_uncertainty

    if effective_edge is None or effective_edge <= 0:
        blockers.append("NET_EDGE_NOT_POSITIVE")

    if blockers:
        return _zero_result(
            available=available,
            raw_amount=raw_amount,
            safe_quote_reserve=safe_quote_reserve,
            risk_log_distance=risk_log_distance,
            gap_multiplier=gap_multiplier,
            calibration=calibration,
            empirical_cost_uncertainty=empirical_cost_uncertainty,
            effective_edge=effective_edge,
            cost_complete=cost_complete,
            blockers=blockers,
        )

    risk_retention = math.exp(-risk_log_distance)
    stop_loss_fraction = 1.0 - risk_retention

    base_risk_notional = min(raw_amount, available)
    raw_stop_risk_budget = base_risk_notional * stop_loss_fraction
    stop_risk_budget = min(
        raw_stop_risk_budget,
        account_risk_budget,
    )

    tail_loss_fraction = min(
        1.0,
        stop_loss_fraction * gap_multiplier,
    )

    tail_risk_amount_cap = (
        stop_risk_budget / tail_loss_fraction
        if tail_loss_fraction > 0
        else 0.0
    )

    risk_adjusted_exit_capacity = (
        safe_quote_reserve * risk_retention
    )

    empirical_exit_cap = (
        risk_adjusted_exit_capacity / gap_multiplier
    )

    amount = max(
        0.0,
        min(
            raw_amount,
            available,
            empirical_exit_cap,
            tail_risk_amount_cap,
        ),
    )

    risk = amount * tail_loss_fraction

    return {
        "entry_amount_usdt": amount,
        "risk_amount_usdt": risk,
        "capital_before_usdt": available,
        "capital_after_entry_usdt": max(0.0, available - amount),
        "position_size_pct": (
            100.0 * amount / available
            if available > 0
            else 0.0
        ),
        "sizing_reason": (
            "EMPIRICAL_GAP_EXIT_CAPACITY"
            if amount > 0
            else "MATHEMATICAL_POSITION_SIZE_ZERO"
        ),
        "formula_authority": "DATA_DERIVED",
        "magic_percentage_rule": False,
        "sizing_model": "EMPIRICAL_GAP_EXIT_CAPACITY_V2",
        "blockers": [],
        "raw_plan_amount_usdt": raw_amount,
        "safe_quote_reserve_usd": safe_quote_reserve,
        "risk_log_distance": risk_log_distance,
        "risk_retention": risk_retention,
        "raw_stop_risk_budget_usdt": raw_stop_risk_budget,
        "stop_risk_budget_usdt": stop_risk_budget,
        "account_risk_budget_usdt": account_risk_budget,
        "account_risk_statistic": calibration.get(
            "account_risk_statistic"
        ),
        "account_risk_samples": calibration.get(
            "account_risk_samples"
        ),
        "tail_loss_fraction": tail_loss_fraction,
        "tail_risk_amount_cap_usdt": tail_risk_amount_cap,
        "risk_adjusted_exit_capacity_usdt": (
            risk_adjusted_exit_capacity
        ),
        "empirical_exit_capacity_usdt": empirical_exit_cap,
        "gap_multiplier": gap_multiplier,
        "gap_samples": calibration.get("gap_samples"),
        "empirical_cost_uncertainty_fraction": (
            empirical_cost_uncertainty
        ),
        "cost_samples": calibration.get("cost_samples"),
        "effective_edge_fraction": effective_edge,
        "cost_complete": cost_complete,
        "kelly_diagnostic_only": True,
    }
