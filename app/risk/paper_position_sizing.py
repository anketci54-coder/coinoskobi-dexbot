import json
import math
import re
import sqlite3
import statistics
from datetime import datetime
from pathlib import Path

from app.strategy.mathematical_trade_plan import (
    buy_token_amount,
    initial_net_risk_usdt,
)


PAPER_CAPITAL_USDT = 10_000.0
PAPER_OUTCOME_EXCLUSIONS_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "paper_outcome_exclusions.json"
)

_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)


class OutcomeExclusionRegistryError(ValueError):
    pass


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


def _accounting_quantum(balance):
    balance = _positive(balance)

    if balance is None:
        return 0.0

    return (
        balance
        - math.nextafter(
            balance,
            -math.inf,
        )
    )


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


def _valid_timestamp(value):
    if not isinstance(value, str):
        return False

    value = value.strip()

    if not value or _TIMESTAMP_RE.fullmatch(value) is None:
        return False

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False

    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() is not None
    )


def _load_outcome_exclusions(path=None):
    path = Path(
        path
        or PAPER_OUTCOME_EXCLUSIONS_PATH
    )

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise OutcomeExclusionRegistryError(
            "OUTCOME_EXCLUSION_REGISTRY_UNREADABLE"
        ) from exc

    if (
        not isinstance(payload, dict)
        or payload.get("version") != 1
        or not isinstance(
            payload.get("exclusions"),
            list,
        )
    ):
        raise OutcomeExclusionRegistryError(
            "OUTCOME_EXCLUSION_REGISTRY_INVALID"
        )

    exclusions = []

    for raw in payload["exclusions"]:
        if not isinstance(raw, dict):
            raise OutcomeExclusionRegistryError(
                "OUTCOME_EXCLUSION_ROW_INVALID"
            )

        required = (
            "source_table",
            "position_id",
            "created_at",
            "closed_at",
        )

        if any(
            name not in raw
            for name in required
        ):
            raise OutcomeExclusionRegistryError(
                "OUTCOME_EXCLUSION_FINGERPRINT_INCOMPLETE"
            )

        source_raw = raw.get("source_table")
        position_raw = raw.get("position_id")
        created_raw = raw.get("created_at")
        closed_raw = raw.get("closed_at")

        if (
            not isinstance(source_raw, str)
            or not isinstance(created_raw, str)
            or not isinstance(closed_raw, str)
            or isinstance(position_raw, bool)
            or not isinstance(position_raw, int)
        ):
            raise OutcomeExclusionRegistryError(
                "OUTCOME_EXCLUSION_FINGERPRINT_INVALID"
            )

        source_table = source_raw.strip()
        created_at = created_raw.strip()
        closed_at = closed_raw.strip()
        position_id = position_raw

        if (
            source_table not in {
                "paper_trades",
                "paper_trades_archive",
            }
            or position_id <= 0
            or not _valid_timestamp(created_at)
            or not _valid_timestamp(closed_at)
        ):
            raise OutcomeExclusionRegistryError(
                "OUTCOME_EXCLUSION_FINGERPRINT_INVALID"
            )

        exclusions.append({
            "source_table": source_table,
            "position_id": position_id,
            "created_at": created_at,
            "closed_at": closed_at,
            "reason": str(
                raw.get("reason")
                or "OUTCOME_EXCLUDED"
            ),
        })

    return exclusions


def _outcome_is_excluded(
    row,
    table_name,
    exclusions,
):
    position_id = row["position_id"]
    created_at = row["created_at"]
    closed_at = row["closed_at"]

    if (
        table_name not in {
            "paper_trades",
            "paper_trades_archive",
        }
        or isinstance(position_id, bool)
        or not isinstance(position_id, int)
        or position_id <= 0
        or not _valid_timestamp(created_at)
        or not _valid_timestamp(closed_at)
    ):
        raise OutcomeExclusionRegistryError(
            "OUTCOME_FINGERPRINT_INVALID"
        )

    created_at = created_at.strip()
    closed_at = closed_at.strip()

    for exclusion in exclusions:
        if (
            exclusion["source_table"] == table_name
            and exclusion["position_id"] == position_id
            and exclusion["created_at"] == created_at
            and exclusion["closed_at"] == closed_at
        ):
            return True

    return False


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


def _active_paper_run(conn):
    """Return the single active paper run, if run accounting exists."""
    exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table'
          AND name='paper_runs'
        """
    ).fetchone()

    if exists is None:
        return None

    rows = conn.execute(
        """
        SELECT
            id,
            run_key,
            starting_capital_usdt,
            start_trade_id,
            start_realization_id,
            start_candidate_id,
            started_at
        FROM paper_runs
        WHERE status='ACTIVE'
        ORDER BY id DESC
        LIMIT 2
        """
    ).fetchall()

    if not rows:
        return None

    if len(rows) != 1:
        raise RuntimeError(
            "PAPER_ACTIVE_RUN_CARDINALITY_INVALID"
        )

    row = rows[0]

    return {
        "id": int(row[0]),
        "run_key": str(row[1]),
        "starting_capital_usdt": float(row[2]),
        "start_trade_id": int(row[3]),
        "start_realization_id": int(row[4]),
        "start_candidate_id": int(row[5]),
        "started_at": float(row[6]),
    }


def paper_available_capital_usdt(
    conn,
    starting_capital_usdt=PAPER_CAPITAL_USDT,
):
    """Durable free-cash truth for the active PAPER 10K run."""
    active_run = _active_paper_run(conn)

    if active_run is not None:
        starting = _number(
            active_run["starting_capital_usdt"]
        )
        start_trade_id = int(
            active_run["start_trade_id"]
        )
    else:
        starting = _number(
            starting_capital_usdt
        )
        start_trade_id = 0

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
          AND id > ?
        """,
        (start_trade_id,),
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
        "account_risk_budget_fraction": None,
        "account_risk_statistic": None,
        "gap_samples": 0,
        "cost_samples": 0,
        "account_risk_samples": 0,
        "excluded_samples": 0,
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
        "id",
        "created_at",
        "closed_at",
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
            {expressions['id']} AS position_id,
            {expressions['created_at']} AS created_at,
            {expressions['closed_at']} AS closed_at,
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


def _modeled_known_cost_fraction(row):
    amount = _positive(row["entry_amount_usdt"])
    if amount is None:
        return None

    plan = _json_dict(row["mathematical_plan_json"])
    cost_model = (
        plan.get("cost_model")
        if isinstance(plan.get("cost_model"), dict)
        else {}
    )

    sell_retention = (
        1.0
        if "sell_retention_known" not in cost_model
        else _number(
            cost_model.get("sell_retention_known")
        )
    )

    if (
        sell_retention is None
        or sell_retention <= 0
        or sell_retention > 1
    ):
        return 0.0

    # gross_pnl_usdt is already based on the post-buy token amount.
    # Therefore gross-to-net observed cost contains only exit-side
    # deductions; subtracting buy-side friction here would understate
    # empirical execution-cost uncertainty.
    gross_pnl = _number(row["gross_pnl_usdt"])
    gross_exit_proceeds = (
        amount + gross_pnl
        if gross_pnl is not None
        else None
    )
    if (
        gross_exit_proceeds is None
        or not math.isfinite(gross_exit_proceeds)
        or gross_exit_proceeds < 0
    ):
        return 0.0

    retention_cost = (
        max(
            0.0,
            1.0 - sell_retention,
        )
        * gross_exit_proceeds
        / amount
    )

    sell_gas = max(
        0.0,
        _number(cost_model.get("sell_gas_usd")) or 0.0,
    )
    gas_cost = sell_gas / amount

    value = retention_cost + gas_cost
    return value if math.isfinite(value) else None


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
    Learn gap overshoot, cost uncertainty, and capital-normalized account-loss
    budget from durable closed paper outcomes only. No fixed risk
    percentage is introduced.

    Outcomes explicitly listed in the audited exclusion registry are
    omitted from calibration only. Their durable accounting remains intact.
    Registry integrity is fail-closed: if exclusions cannot be proven,
    calibration is unavailable rather than silently ingesting bad outcomes.
    """
    path = Path(db_path)

    try:
        exclusions = _load_outcome_exclusions()
    except OutcomeExclusionRegistryError:
        return _calibration_empty(
            "OUTCOME_EXCLUSION_REGISTRY_INVALID"
        )

    if not path.exists():
        return _calibration_empty("OUTCOME_DB_MISSING")

    excluded_samples = 0

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
            """,
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
            for row in _closed_outcome_rows(
                db,
                table_name,
            ):
                if _outcome_is_excluded(
                    row,
                    table_name,
                    exclusions,
                ):
                    excluded_samples += 1
                    continue

                rows.append(row)

        db.close()

    except OutcomeExclusionRegistryError as exc:
        db.close()
        return _calibration_empty(
            str(exc)
        )

    except sqlite3.Error:
        return _calibration_empty("OUTCOME_DB_READ_FAILED")

    gap_ratios = []
    cost_residuals = []
    account_losses = []

    for row in rows:
        historical_plan = _json_dict(row["mathematical_plan_json"])
        capital_evidence = historical_plan.get("capital")
        historical_capital = _positive(
            capital_evidence.get("available_usdt")
            if isinstance(capital_evidence, dict) else None
        )
        if historical_capital is None:
            return _calibration_empty("OUTCOME_CAPITAL_PROVENANCE_INVALID")
        calibration_quantum = _accounting_quantum(historical_capital)
        entry_amount = _positive(
            row["entry_amount_usdt"]
        )

        # Historical trades whose notional could not change the
        # historical account balance at IEEE-754 precision are
        # accounting artifacts, not empirical risk observations.
        # Exclude them from every calibration statistic rather
        # than allowing legacy float dust to poison the sample.
        if (
            entry_amount is None
            or (
                calibration_quantum > 0.0
                and entry_amount < calibration_quantum
            )
        ):
            continue

        planned_loss = _planned_loss_fraction(row)
        observed_loss = _observed_market_loss_fraction(row)
        cost_fraction = _observed_cost_fraction(row)
        modeled_known_cost = _modeled_known_cost_fraction(row)
        account_loss = _observed_account_loss_usdt(row)

        if (
            account_loss is not None
            and math.isfinite(account_loss)
        ):
            account_losses.append(account_loss / historical_capital)

        if (
            cost_fraction is not None
            and modeled_known_cost is not None
            and math.isfinite(cost_fraction)
            and math.isfinite(modeled_known_cost)
        ):
            # The current plan already subtracts measured known friction.
            # Calibration must therefore learn only the unexplained residual;
            # subtracting total historical execution cost again double-counts
            # known route/tax/gas economics and can zero valid PAPER sizing.
            cost_residuals.append(
                max(
                    0.0,
                    cost_fraction - modeled_known_cost,
                )
            )

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
        "account_risk_budget_fraction": account_risk_budget,
        "account_risk_statistic": (
            "MEDIAN_REALIZED_LOSS_CAPITAL_FRACTION"
            if account_risk_budget is not None
            else None
        ),
        "gap_samples": len(gap_ratios),
        "cost_samples": len(positive_costs),
        "account_risk_samples": len(account_losses),
        "excluded_samples": excluded_samples,
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
        "capital_bound_usdt": available,
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
        "account_risk_budget_fraction": calibration.get(
            "account_risk_budget_fraction"
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


def _bind_final_trade_plan(plan, amount, available):
    if not isinstance(plan, dict):
        return {
            "token_amount": 0.0,
            "initial_sl": None,
            "initial_net_risk_usdt": None,
            "tp1_activation_price": None,
        }

    capital = plan.get("capital")
    if not isinstance(capital, dict):
        capital = {}
        plan["capital"] = capital

    entry = plan.get("entry")
    if not isinstance(entry, dict):
        entry = {}
        plan["entry"] = entry

    position = plan.get("position")
    if not isinstance(position, dict):
        position = {}
        plan["position"] = position

    sl = plan.get("sl")
    if not isinstance(sl, dict):
        sl = {}
        plan["sl"] = sl

    tp1 = plan.get("tp1")
    if not isinstance(tp1, dict):
        tp1 = {}
        plan["tp1"] = tp1

    cost_model = plan.get("cost_model")
    if not isinstance(cost_model, dict):
        cost_model = {}
        plan["cost_model"] = cost_model

    entry_price = _positive(entry.get("price"))
    initial_sl = _positive(sl.get("initial_price"))

    token_amount = (
        buy_token_amount(
            amount,
            entry_price,
            cost_model,
        )
        if entry_price is not None
        else 0.0
    )

    initial_net_risk = (
        initial_net_risk_usdt(
            token_amount,
            amount,
            initial_sl,
            cost_model,
        )
        if initial_sl is not None
        else None
    )

    sell_retention = _number(
        cost_model.get("sell_retention_known")
    )
    sell_gas = max(
        0.0,
        _number(cost_model.get("sell_gas_usd")) or 0.0,
    )

    tp1_activation = None
    if (
        token_amount > 0
        and sell_retention is not None
        and sell_retention > 0
        and initial_net_risk is not None
    ):
        tp1_activation = (
            amount
            + initial_net_risk
            + sell_gas
        ) / (
            token_amount
            * sell_retention
        )

    capital["entry_amount_usdt"] = amount
    capital["position_fraction_of_available"] = (
        amount / available
        if available > 0
        else 0.0
    )
    position["token_amount"] = token_amount
    position["initial_risk_usdt"] = initial_net_risk
    tp1["activation_price"] = tp1_activation

    return {
        "token_amount": token_amount,
        "initial_sl": initial_sl,
        "initial_net_risk_usdt": initial_net_risk,
        "tp1_activation_price": tp1_activation,
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
    account_risk_fraction = _positive(calibration.get("account_risk_budget_fraction"))
    account_risk_budget = (
        available * min(1.0, account_risk_fraction)
        if account_risk_fraction is not None else None
    )

    blockers = []
    opportunity = (plan.get("market_context") or {}).get("opportunity") or {}
    if opportunity.get("catastrophic_reserve_collapse"):
        blockers.append("CATASTROPHIC_RESERVE_COLLAPSE")
    if plan.get("hard_block"):
        blockers.append("HARD_BLOCK")
    if plan.get("sellability_status") not in (
        None,
        "SELLABILITY_OK",
        "SELLABILITY_UNKNOWN",
    ):
        blockers.append("SELLABILITY_NOT_OK")
    if plan.get("paper_eligible") is False:
        blockers.append("PLAN_NOT_PAPER_ELIGIBLE")

    calibration_reason = str(
        calibration.get("reason")
        or ""
    )

    if calibration_reason in {
        "OUTCOME_EXCLUSION_REGISTRY_INVALID",
        "OUTCOME_FINGERPRINT_INVALID",
        "OUTCOME_CAPITAL_PROVENANCE_INVALID",
    }:
        blockers.append(
            calibration_reason
        )

    lp_unverified = liquidity_capacity_source != "VERIFIED_LP_PROTECTION"
    # Observed reserves remain shadow evidence, never withdrawal protection.
    # This blocker also excludes the PAPER calibration bootstrap path.
    if lp_unverified:
        blockers.append("LP_WITHDRAWAL_PROTECTION_UNVERIFIED")
    observed_reserve = _positive(capital.get("observed_min_quote_reserve_usd"))
    empirical_exit_ready = (
        liquidity_capacity_source == "EMPIRICAL_RESERVE_FLOOR"
        and (_number(capital.get("reserve_observation_count")) or 0) >= 2
        and observed_reserve is not None
        and safe_quote_reserve is not None
        and safe_quote_reserve <= observed_reserve
        and plan.get("sellability_status") in {
            "SELLABILITY_OK",
            "SELLABILITY_UNKNOWN",
        }
        and plan.get("paper_eligible") is True
        and opportunity.get("state") in {"HOT", "WARM"}
    )
    plan_blockers = plan.get("blockers") or []
    if plan_blockers:
        blockers.append("PLAN_BLOCKED")
    if lp_unverified and not empirical_exit_ready:
        blockers.append("EMPIRICAL_EXIT_EVIDENCE_INVALID")

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
            or empirical_cost_uncertainty < 0
        ):
            effective_edge = None
            blockers.append("COST_UNCERTAINTY_UNOBSERVED")
        else:
            effective_edge = known_edge - empirical_cost_uncertainty

    if effective_edge is None or effective_edge <= 0:
        blockers.append("NET_EDGE_NOT_POSITIVE")

    measured_stats = plan.get("statistics") or plan.get("market_statistics") or {}
    if not isinstance(measured_stats, dict):
        measured_stats = {}
    second_moment = _positive(measured_stats.get("second_moment"))
    measured_tail = _positive(measured_stats.get("tail_risk_fraction"))
    if second_moment is None or measured_tail is None or measured_tail > 1:
        blockers.append("RETURN_RISK_UNOBSERVABLE")
    # Recompute the capital fraction from current net edge and measured risk.
    # Neither a stale raw USDT proposal nor concurrent slot count sets size.
    stop_fraction = -math.expm1(-risk_log_distance) if risk_log_distance else 0.0
    risk_fraction = max(stop_fraction, measured_tail or 0.0)
    capital_fraction = (
        min(1.0, math.log1p(effective_edge) / second_moment)
        * effective_edge / (effective_edge + risk_fraction)
        if effective_edge is not None and effective_edge > 0 and second_moment else 0.0
    )
    capital_notional = available * capital_fraction
    liquidity_edge_cap = (
        safe_quote_reserve * effective_edge
        if safe_quote_reserve and effective_edge and effective_edge > 0 else 0.0
    )

    entry = plan.get("entry") if isinstance(plan.get("entry"), dict) else {}
    current_price = _positive(entry.get("price"))
    statistics = plan.get("statistics") if isinstance(plan.get("statistics"), dict) else {}
    price_evidence = statistics.get("prices") or []
    prior_prices = [
        value for value in (_positive(item) for item in price_evidence[:-1])
        if value is not None
    ] if isinstance(price_evidence, (list, tuple)) else []
    anchor_price = prior_prices[-1] if prior_prices else None
    observed_moves = [
        abs(math.log(current / previous))
        for previous, current in zip(prior_prices, prior_prices[1:])
        if previous > 0 and current > 0
    ]
    observed_move = max(observed_moves, default=0.0)
    edge_move = _positive(effective_edge)
    entry_timing = {
        "entry_zone_low": None,
        "entry_zone_high": None,
        "preferred_entry": None,
        "chase_limit": None,
        "immediate_entry_allowed": False,
    }
    timing_ready = False
    vur_kac_gate = plan.get("vur_kac_entry")
    vur_kac_ready = not (
        isinstance(vur_kac_gate, dict)
        and vur_kac_gate.get("enforced")
    ) or bool(vur_kac_gate.get("ready"))
    admission = plan.get("paper_admission") or {}
    vur_kac_ready = vur_kac_ready or (
        plan.get("paper_eligible") is True
        and not plan.get("blockers")
        and not plan.get("hard_block")
        and plan.get("sellability_status") in {
            "SELLABILITY_OK",
            "SELLABILITY_UNKNOWN",
        }
        and admission.get("mode") == "EARLY_EMPIRICAL"
        and admission.get("early_paper_admission") is True
        and admission.get("paper_only") is True
    )
    if current_price is not None and anchor_price is not None and edge_move is not None:
        tolerated_move = min(edge_move, observed_move)
        entry_timing.update({
            "entry_zone_low": anchor_price * math.exp(-tolerated_move),
            "entry_zone_high": anchor_price,
            "preferred_entry": anchor_price * math.exp(-tolerated_move / 2.0),
            "chase_limit": anchor_price * math.exp(tolerated_move),
        })
        if current_price > entry_timing["chase_limit"]:
            blockers.append("ENTRY_ABOVE_CHASE_LIMIT")
        timing_ready = (
            entry_timing["entry_zone_low"]
            <= current_price
            <= entry_timing["chase_limit"]
        )

    accounting_quantum = _accounting_quantum(
        available
    )

    def economic_blockers(amount):
        if amount <= 0:
            return ["MATHEMATICAL_POSITION_SIZE_ZERO"]
        if amount < accounting_quantum:
            return ["ENTRY_AMOUNT_BELOW_ACCOUNTING_PRECISION"]
        buy_gas = max(0.0, _number(cost_model.get("buy_gas_usd")) or 0.0)
        sell_gas = max(0.0, _number(cost_model.get("sell_gas_usd")) or 0.0)
        # Quoted net edge includes proportional buy/sell friction, not gas.
        # Residual uncertainty is charged on the entire final debit, just as
        # historical calibration measures it, not only the post-gas notional.
        quoted_edge = full_edge if cost_complete else known_edge
        residual = 0.0 if cost_complete else empirical_cost_uncertainty
        final_net = (
            amount * quoted_edge - buy_gas * (1.0 + quoted_edge)
            - sell_gas - amount * residual
        )
        if not math.isfinite(final_net) or final_net <= 0:
            return ["FIXED_COST_NET_EDGE_NOT_POSITIVE"]
        return []

    def blocked_amount(reasons):
        result = _zero_result(
            available=available, raw_amount=raw_amount,
            safe_quote_reserve=safe_quote_reserve,
            risk_log_distance=risk_log_distance, gap_multiplier=gap_multiplier,
            calibration=calibration,
            empirical_cost_uncertainty=empirical_cost_uncertainty,
            effective_edge=effective_edge, cost_complete=cost_complete,
            blockers=reasons,
        )
        result.update(entry_timing)
        return result

    # Missing historical gap evidence uses total loss during PAPER bootstrap.
    # Reserve persistence never becomes verified withdrawal protection.
    empirical_liquidity_bootstrap = empirical_exit_ready
    bootstrap_blockers = {
        "GAP_RISK_UNOBSERVED",
        "ACCOUNT_RISK_BUDGET_UNOBSERVED",
    }

    paper_calibration_bootstrap = (
        bool(plan.get("paper_eligible"))
        and raw_amount > 0
        and available > 0
        and safe_quote_reserve is not None
        and risk_log_distance is not None
        and (cost_complete or empirical_cost_uncertainty is not None)
        and effective_edge is not None
        and effective_edge > 0
        and (
            liquidity_capacity_source != "EMPIRICAL_RESERVE_FLOOR"
            or empirical_liquidity_bootstrap
        )
        and bool(blockers)
        and set(blockers).issubset(
            bootstrap_blockers
        )
    )

    if paper_calibration_bootstrap:
        risk_retention = math.exp(-risk_log_distance)
        stop_loss_fraction = 1.0 - risk_retention
        base_risk_notional = capital_notional
        bootstrap_risk_budget = (
            base_risk_notional * stop_loss_fraction
        )

        # Gap risk is unobserved during bootstrap. Fail closed by assuming
        # the calibration position can lose its entire notional before the
        # next trustworthy observation. Therefore notional cannot exceed
        # the plan-derived stop-risk budget.
        bootstrap_tail_loss_fraction = 1.0
        bootstrap_amount = max(
            0.0,
            min(
                capital_notional,
                available,
                liquidity_edge_cap,
                safe_quote_reserve * math.exp(-risk_log_distance),
                bootstrap_risk_budget,
                account_risk_budget if account_risk_budget is not None else bootstrap_risk_budget,
            ),
        )

        if (
            bootstrap_amount > 0.0
            and accounting_quantum > 0.0
            and bootstrap_amount < accounting_quantum
        ):
            result = _zero_result(
                available=available,
                raw_amount=raw_amount,
                safe_quote_reserve=safe_quote_reserve,
                risk_log_distance=risk_log_distance,
                gap_multiplier=gap_multiplier,
                calibration=calibration,
                empirical_cost_uncertainty=(
                    empirical_cost_uncertainty
                ),
                effective_edge=effective_edge,
                cost_complete=cost_complete,
                blockers=[
                    "ENTRY_AMOUNT_BELOW_"
                    "ACCOUNTING_PRECISION"
                ],
            )
            result.update(entry_timing)
            return result

        economic_reasons = economic_blockers(bootstrap_amount)
        if economic_reasons:
            return blocked_amount(economic_reasons)

        if bootstrap_amount > 0:
            risk = (
                bootstrap_amount
                * bootstrap_tail_loss_fraction
            )

            bound_plan = _bind_final_trade_plan(
                plan,
                bootstrap_amount,
                available,
            )

            result = {
                "entry_amount_usdt": bootstrap_amount,
                "risk_amount_usdt": risk,
                "capital_before_usdt": available,
                "capital_after_entry_usdt": max(
                    0.0,
                    available - bootstrap_amount,
                ),
                "position_size_pct": (
                    100.0 * bootstrap_amount / available
                    if available > 0
                    else 0.0
                ),
                "sizing_reason": (
                    "PAPER_CALIBRATION_BOOTSTRAP"
                ),
                "formula_authority": "DATA_DERIVED",
                "magic_percentage_rule": False,
                "sizing_model": (
                    "PAPER_CALIBRATION_BOOTSTRAP_V2"
                ),
                "paper_calibration_bootstrap": True,
                "liquidity_protection_unverified": empirical_liquidity_bootstrap,
                "capital_bound_usdt": available,
                "blockers": [],
                "raw_plan_amount_usdt": raw_amount,
                "safe_quote_reserve_usd": safe_quote_reserve,
                "risk_log_distance": risk_log_distance,
                "risk_retention": risk_retention,
                "stop_loss_fraction": stop_loss_fraction,
                "bootstrap_tail_loss_fraction": (
                    bootstrap_tail_loss_fraction
                ),
                "bootstrap_risk_budget_usdt": (
                    bootstrap_risk_budget
                ),
                "stop_risk_budget_usdt": (
                    bootstrap_risk_budget
                ),
                "known_net_edge_fraction": known_edge,
                "full_net_edge_fraction": full_edge,
                "effective_edge_fraction": effective_edge,
                "empirical_cost_uncertainty_fraction": (
                    empirical_cost_uncertainty
                ),
                "gap_samples": calibration.get(
                    "gap_samples"
                ),
                "cost_samples": calibration.get(
                    "cost_samples"
                ),
                "account_risk_samples": calibration.get(
                    "account_risk_samples"
                ),
                "canonical_token_amount": (
                    bound_plan["token_amount"]
                ),
                "canonical_initial_sl": (
                    bound_plan["initial_sl"]
                ),
                "canonical_initial_net_risk_usdt": (
                    bound_plan["initial_net_risk_usdt"]
                ),
                "canonical_tp1_activation_price": (
                    bound_plan["tp1_activation_price"]
                ),
                "kelly_diagnostic_only": True,
                **entry_timing,
            }
            result["immediate_entry_allowed"] = (
                timing_ready and vur_kac_ready
            )
            return result

    if blockers:
        result = _zero_result(
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
        result.update(entry_timing)
        return result

    risk_retention = math.exp(-risk_log_distance)
    stop_loss_fraction = 1.0 - risk_retention

    base_risk_notional = capital_notional
    raw_stop_risk_budget = base_risk_notional * stop_loss_fraction
    capped_stop_risk_budget = min(
        raw_stop_risk_budget,
        account_risk_budget,
    )

    tail_loss_fraction = (
        1.0 if lp_unverified else min(
            1.0, max(measured_tail, stop_loss_fraction * max(1.0, gap_multiplier)),
        )
    )

    tail_risk_amount_cap = (
        capped_stop_risk_budget / tail_loss_fraction
        if tail_loss_fraction > 0
        else 0.0
    )

    risk_adjusted_exit_capacity = (
        safe_quote_reserve * risk_retention
    )

    empirical_exit_cap = (
        risk_adjusted_exit_capacity / max(1.0, gap_multiplier)
    )

    amount = max(
        0.0,
        min(
            capital_notional,
            available,
            liquidity_edge_cap,
            empirical_exit_cap,
            tail_risk_amount_cap,
        ),
    )

    # A paper debit smaller than the next representable
    # downward account-capital step cannot be represented
    # faithfully by float accounting. Derive the floor from
    # IEEE-754 spacing instead of inventing a trade minimum.
    if (
        amount > 0.0
        and accounting_quantum > 0.0
        and amount < accounting_quantum
    ):
        return _zero_result(
            available=available,
            raw_amount=raw_amount,
            safe_quote_reserve=(
                safe_quote_reserve
            ),
            risk_log_distance=(
                risk_log_distance
            ),
            gap_multiplier=gap_multiplier,
            calibration=calibration,
            empirical_cost_uncertainty=(
                empirical_cost_uncertainty
            ),
            effective_edge=effective_edge,
            cost_complete=cost_complete,
            blockers=[
                "ENTRY_AMOUNT_BELOW_"
                "ACCOUNTING_PRECISION"
            ],
        )

    economic_reasons = economic_blockers(amount)
    if economic_reasons:
        return blocked_amount(economic_reasons)

    risk = amount * tail_loss_fraction
    bound_plan = _bind_final_trade_plan(
        plan,
        amount,
        available,
    )

    result = {
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
        "capital_bound_usdt": available,
        "blockers": [],
        "raw_plan_amount_usdt": raw_amount,
        "safe_quote_reserve_usd": safe_quote_reserve,
        "risk_log_distance": risk_log_distance,
        "risk_retention": risk_retention,
        "raw_stop_risk_budget_usdt": raw_stop_risk_budget,
        "stop_risk_budget_usdt": raw_stop_risk_budget,
        "capped_stop_risk_budget_usdt": capped_stop_risk_budget,
        "account_risk_budget_usdt": account_risk_budget,
        "account_risk_statistic": calibration.get(
            "account_risk_statistic"
        ),
        "account_risk_samples": calibration.get(
            "account_risk_samples"
        ),
        "tail_loss_fraction": tail_loss_fraction,
        "liquidity_protection_unverified": lp_unverified,
        "account_risk_budget_fraction": account_risk_fraction,
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
        **entry_timing,
        "canonical_token_amount": bound_plan["token_amount"],
        "canonical_initial_sl": bound_plan["initial_sl"],
        "canonical_initial_net_risk_usdt": (
            bound_plan["initial_net_risk_usdt"]
        ),
        "canonical_tp1_activation_price": (
            bound_plan["tp1_activation_price"]
        ),
    }
    result["immediate_entry_allowed"] = (
        timing_ready and vur_kac_ready
    )
    return result
