import json
import math
import sqlite3
import statistics
from pathlib import Path


# Paper account capital.
# Not a trade allocation percentage.
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


def _find_number(node, names):
    """
    Find one named numeric measurement anywhere
    inside a mathematical plan.

    This is compatibility-only because historical
    plan nesting may differ.
    """

    if isinstance(node, dict):
        for key in names:
            if key in node:
                value = _number(node.get(key))

                if value is not None:
                    return value

        for value in node.values():
            result = _find_number(
                value,
                names,
            )

            if result is not None:
                return result

    elif isinstance(node, (list, tuple)):
        for value in node:
            result = _find_number(
                value,
                names,
            )

            if result is not None:
                return result

    return None


def _json_dict(raw):
    if isinstance(raw, dict):
        return raw

    if not raw:
        return {}

    try:
        result = json.loads(raw)
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return {}

    return (
        result
        if isinstance(result, dict)
        else {}
    )


def _empirical_outcome_calibration(
    db_path="data/paper_trades.db",
):
    """
    Learn only from observed closed mathematical
    paper outcomes.

    gap_multiplier:
        actual downside / downside implied by the
        latest persisted mathematical floor.

    cost_uncertainty_fraction:
        robust center of positive observed
        gross-to-net execution cost drag,
        relative to entry size.

    No hand-picked percentage or risk coefficient
    is introduced here.
    """

    path = Path(db_path)

    if not path.exists():
        return {
            "ready": False,
            "reason": "OUTCOME_DB_MISSING",
            "gap_multiplier": None,
            "cost_uncertainty_fraction": None,
            "gap_samples": 0,
            "cost_samples": 0,
        }

    try:
        db = sqlite3.connect(
            f"file:{path}?mode=ro",
            uri=True,
        )
        db.row_factory = sqlite3.Row

        active_table_exists = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name='paper_trades'
            """
        ).fetchone()

        if active_table_exists is None:
            db.close()

            return {
                "ready": False,
                "reason": "PAPER_TRADES_MISSING",
                "gap_multiplier": None,
                "cost_uncertainty_fraction": None,
                "gap_samples": 0,
                "cost_samples": 0,
            }

        required = {
            "status",
            "entry_price",
            "current_price",
            "entry_amount_usdt",
            "net_pnl",
            "mathematical_plan_json",
            "math_state_json",
        }

        active_columns = {
            row[1]
            for row in db.execute(
                "PRAGMA table_info(paper_trades)"
            ).fetchall()
        }

        if not required.issubset(
            active_columns
        ):
            db.close()

            return {
                "ready": False,
                "reason": "OUTCOME_COLUMNS_INCOMPLETE",
                "gap_multiplier": None,
                "cost_uncertainty_fraction": None,
                "gap_samples": 0,
                "cost_samples": 0,
            }

        rows = []

        # Performance/accounting stays on the active
        # paper table. Risk calibration may also learn
        # from genuine closed paper outcomes preserved
        # by the canonical archive reset.
        for table_name in (
            "paper_trades_archive",
            "paper_trades",
        ):
            table_exists = db.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type='table'
                  AND name=?
                """,
                (table_name,),
            ).fetchone()

            if table_exists is None:
                continue

            columns = {
                row[1]
                for row in db.execute(
                    f"PRAGMA table_info({table_name})"
                ).fetchall()
            }

            if not required.issubset(
                columns
            ):
                continue

            gross_pnl_expr = (
                "gross_pnl_usdt"
                if "gross_pnl_usdt" in columns
                else "NULL"
            )

            net_pnl_usdt_expr = (
                "net_pnl_usdt"
                if "net_pnl_usdt" in columns
                else "NULL"
            )

            rows.extend(
                db.execute(
                    f"""
                    SELECT
                        entry_price,
                        current_price,
                        entry_amount_usdt,
                        net_pnl,
                        mathematical_plan_json,
                        math_state_json,
                        {gross_pnl_expr}
                            AS gross_pnl_usdt,
                        {net_pnl_usdt_expr}
                            AS net_pnl_usdt
                    FROM {table_name}
                    WHERE status='CLOSED'
                      AND mathematical_plan_json
                          IS NOT NULL
                    """
                ).fetchall()
            )

        db.close()

    except sqlite3.Error:
        return {
            "ready": False,
            "reason": "OUTCOME_DB_READ_FAILED",
            "gap_multiplier": None,
            "cost_uncertainty_fraction": None,
            "gap_samples": 0,
            "cost_samples": 0,
        }

    gap_ratios = []
    cost_residuals = []

    for row in rows:
        entry = _positive(
            row["entry_price"]
        )
        current = _positive(
            row["current_price"]
        )
        amount = _positive(
            row["entry_amount_usdt"]
        )
        net_pnl = _number(
            row["net_pnl"]
        )

        if (
            entry is None
            or current is None
            or amount is None
        ):
            continue

        plan = _json_dict(
            row["mathematical_plan_json"]
        )
        state = _json_dict(
            row["math_state_json"]
        )

        stop = _positive(
            state.get("last_stop")
        )

        if stop is None:
            entry_plan = (
                plan.get("entry")
                if isinstance(
                    plan.get("entry"),
                    dict,
                )
                else {}
            )

            stop = _positive(
                entry_plan.get("band_low")
            )

        gross_pnl_usdt = _number(
            row["gross_pnl_usdt"]
        )

        net_pnl_usdt = _number(
            row["net_pnl_usdt"]
        )

        residual = None

        if (
            gross_pnl_usdt is not None
            and net_pnl_usdt is not None
        ):
            # Closed mathematical accounting already
            # includes every partial realization.
            # Therefore gross-minus-net is the observed
            # execution/cost drag without reconstructing
            # the position from the final mark price.
            residual = max(
                0.0,
                (
                    gross_pnl_usdt
                    - net_pnl_usdt
                )
                / amount,
            )

        elif net_pnl is not None:
            # Compatibility for historical rows that
            # predate final gross/net USD accounting.
            actual_return = (
                current / entry
            ) - 1.0

            mark_pnl = (
                amount
                * actual_return
            )

            residual = max(
                0.0,
                (
                    mark_pnl
                    - net_pnl
                )
                / amount,
            )

        if (
            residual is not None
            and math.isfinite(residual)
        ):
            cost_residuals.append(
                residual
            )

        if (
            stop is None
            or stop >= entry
        ):
            continue

        planned_loss_fraction = (
            1.0
            - stop / entry
        )

        actual_loss_fraction = max(
            0.0,
            1.0
            - current / entry,
        )

        if (
            planned_loss_fraction <= 0
            or actual_loss_fraction <= 0
        ):
            continue

        ratio = (
            actual_loss_fraction
            / planned_loss_fraction
        )

        if (
            math.isfinite(ratio)
            and ratio > 0
        ):
            gap_ratios.append(
                ratio
            )

    gap_multiplier = (
        statistics.median(
            gap_ratios
        )
        if gap_ratios
        else None
    )

    positive_cost_residuals = [
        value
        for value in cost_residuals
        if value > 0
    ]

    cost_uncertainty = (
        statistics.median(
            positive_cost_residuals
        )
        if positive_cost_residuals
        else None
    )

    ready = (
        gap_multiplier is not None
        and gap_multiplier > 0
    )

    return {
        "ready": ready,
        "reason": (
            "EMPIRICAL_OUTCOME_CALIBRATION"
            if ready
            else "GAP_RISK_UNOBSERVED"
        ),
        "gap_multiplier": (
            gap_multiplier
        ),
        "cost_uncertainty_fraction": (
            cost_uncertainty
        ),
        "gap_samples": len(
            gap_ratios
        ),
        "cost_samples": len(
            positive_cost_residuals
        ),
    }


def calculate_paper_position_size(
    *,
    mathematical_plan=None,
    available_capital_usdt=None,
    db_path="data/paper_trades.db",
    **_legacy,
):
    """
    Risk-first paper sizing.

    Important properties:

    1. Edge never expands measured exit capacity.
    2. Kelly may remain diagnostic in the plan,
       but cannot override the exit-capacity cap.
    3. Unknown costs are not treated as zero.
       Empirical observed net-cost residual is
       deducted from known-component edge.
    4. Historical observed gap overshoot scales
       down position size.
    5. No fixed position percentage exists.
    """

    plan = (
        mathematical_plan
        if isinstance(
            mathematical_plan,
            dict,
        )
        else {}
    )

    capital = (
        plan.get("capital")
        if isinstance(
            plan.get("capital"),
            dict,
        )
        else {}
    )

    expected = (
        plan.get("expected")
        if isinstance(
            plan.get("expected"),
            dict,
        )
        else {}
    )

    cost_model = (
        plan.get("cost_model")
        if isinstance(
            plan.get("cost_model"),
            dict,
        )
        else {}
    )

    raw_amount = max(
        0.0,
        _number(
            capital.get(
                "entry_amount_usdt"
            )
        )
        or 0.0,
    )

    available = max(
        0.0,
        _number(
            available_capital_usdt
            if (
                available_capital_usdt
                is not None
            )
            else capital.get(
                "available_usdt"
            )
        )
        or 0.0,
    )

    safe_quote_reserve = _positive(
        capital.get(
            "safe_quote_reserve_usd"
        )
    )

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
        expected.get(
            "full_net_edge_fraction"
        )
    )

    known_edge = _number(
        expected.get(
            "known_net_edge_fraction"
        )
    )

    cost_complete = bool(
        cost_model.get(
            "cost_complete"
        )
    )

    calibration = (
        _empirical_outcome_calibration(
            db_path=db_path,
        )
    )

    gap_multiplier = _positive(
        calibration.get(
            "gap_multiplier"
        )
    )

    empirical_cost_uncertainty = (
        _number(
            calibration.get(
                "cost_uncertainty_fraction"
            )
        )
    )

    blockers = []

    if raw_amount <= 0:
        blockers.append(
            "PLAN_AMOUNT_ZERO"
        )

    if available <= 0:
        blockers.append(
            "AVAILABLE_CAPITAL_ZERO"
        )

    if safe_quote_reserve is None:
        blockers.append(
            "EXIT_CAPACITY_UNKNOWN"
        )

    if risk_log_distance is None:
        blockers.append(
            "EMPIRICAL_RISK_DISTANCE_UNKNOWN"
        )

    if gap_multiplier is None:
        blockers.append(
            "GAP_RISK_UNOBSERVED"
        )

    if cost_complete:
        effective_edge = full_edge

        if effective_edge is None:
            blockers.append(
                "FULL_NET_EDGE_UNKNOWN"
            )
    else:
        if (
            known_edge is None
            or empirical_cost_uncertainty
            is None
        ):
            effective_edge = None

            blockers.append(
                "COST_UNCERTAINTY_UNOBSERVED"
            )
        else:
            effective_edge = (
                known_edge
                - empirical_cost_uncertainty
            )

    if (
        effective_edge is None
        or effective_edge <= 0
    ):
        blockers.append(
            "NET_EDGE_NOT_POSITIVE"
        )

    if blockers:
        return {
            "entry_amount_usdt": 0.0,
            "risk_amount_usdt": 0.0,
            "capital_before_usdt": (
                available
            ),
            "capital_after_entry_usdt": (
                available
            ),
            "position_size_pct": 0.0,
            "sizing_reason": (
                "MATHEMATICAL_POSITION_SIZE_ZERO"
            ),
            "formula_authority": (
                "DATA_DERIVED"
            ),
            "magic_percentage_rule": False,
            "sizing_model": (
                "EMPIRICAL_GAP_EXIT_CAPACITY_V1"
            ),
            "blockers": sorted(
                set(blockers)
            ),
            "raw_plan_amount_usdt": (
                raw_amount
            ),
            "safe_quote_reserve_usd": (
                safe_quote_reserve
            ),
            "risk_log_distance": (
                risk_log_distance
            ),
            "gap_multiplier": (
                gap_multiplier
            ),
            "gap_samples": calibration.get(
                "gap_samples"
            ),
            "empirical_cost_uncertainty_fraction": (
                empirical_cost_uncertainty
            ),
            "cost_samples": calibration.get(
                "cost_samples"
            ),
            "effective_edge_fraction": (
                effective_edge
            ),
            "cost_complete": (
                cost_complete
            ),
        }

    # Same exponential relation used by
    # the mathematical stop:
    #
    # stop = entry * exp(-risk_distance)
    #
    # Therefore the exit-capacity retention
    # is data-derived, not a fixed percentage.
    risk_retention = math.exp(
        -risk_log_distance
    )

    risk_adjusted_exit_capacity = (
        safe_quote_reserve
        * risk_retention
    )

    # Scale by the robust empirical center of
    # observed stop-gap overshoot.
    #
    # No edge multiplier is allowed here.
    empirical_exit_cap = (
        risk_adjusted_exit_capacity
        / gap_multiplier
    )

    amount = max(
        0.0,
        min(
            raw_amount,
            available,
            empirical_exit_cap,
        ),
    )

    stop_loss_fraction = (
        1.0
        - risk_retention
    )

    empirical_risk_fraction = min(
        1.0,
        stop_loss_fraction
        * gap_multiplier,
    )

    risk = (
        amount
        * empirical_risk_fraction
    )

    return {
        "entry_amount_usdt": (
            amount
        ),
        "risk_amount_usdt": (
            risk
        ),
        "capital_before_usdt": (
            available
        ),
        "capital_after_entry_usdt": max(
            0.0,
            available - amount,
        ),
        # Reporting only.
        # Never an input rule.
        "position_size_pct": (
            100.0
            * amount
            / available
            if available > 0
            else 0.0
        ),
        "sizing_reason": (
            "EMPIRICAL_GAP_EXIT_CAPACITY"
            if amount > 0
            else (
                "MATHEMATICAL_POSITION_SIZE_ZERO"
            )
        ),
        "formula_authority": (
            "DATA_DERIVED"
        ),
        "magic_percentage_rule": False,
        "sizing_model": (
            "EMPIRICAL_GAP_EXIT_CAPACITY_V1"
        ),
        "blockers": [],
        "raw_plan_amount_usdt": (
            raw_amount
        ),
        "safe_quote_reserve_usd": (
            safe_quote_reserve
        ),
        "risk_log_distance": (
            risk_log_distance
        ),
        "risk_retention": (
            risk_retention
        ),
        "risk_adjusted_exit_capacity_usdt": (
            risk_adjusted_exit_capacity
        ),
        "empirical_exit_capacity_usdt": (
            empirical_exit_cap
        ),
        "gap_multiplier": (
            gap_multiplier
        ),
        "gap_samples": calibration.get(
            "gap_samples"
        ),
        "empirical_cost_uncertainty_fraction": (
            empirical_cost_uncertainty
        ),
        "cost_samples": calibration.get(
            "cost_samples"
        ),
        "effective_edge_fraction": (
            effective_edge
        ),
        "cost_complete": (
            cost_complete
        ),
        "kelly_diagnostic_only": True,
    }
