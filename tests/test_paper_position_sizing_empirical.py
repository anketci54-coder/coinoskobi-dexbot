import math
import pytest

from app.config.trading import MAX_OPEN_PAPER_POSITIONS

from app.risk.paper_position_sizing import (
    calculate_paper_position_size,
)
from app.pipeline.engine import _paper_entry_timing_reason


def _stamp_outcome_fingerprints(db):
    for table in (
        "paper_trades",
        "paper_trades_archive",
    ):
        exists = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name=?
            """,
            (table,),
        ).fetchone()

        if exists is None:
            continue

        columns = {
            row[1]
            for row in db.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

        for name, kind in (
            ("id", "INTEGER"),
            ("created_at", "TEXT"),
            ("closed_at", "TEXT"),
        ):
            if name not in columns:
                db.execute(
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN {name} {kind}"
                )

        rows = db.execute(
            f"SELECT rowid FROM {table} ORDER BY rowid"
        ).fetchall()

        for index, row in enumerate(rows, 1):
            rowid = int(row[0])

            db.execute(
                f"""
                UPDATE {table}
                SET
                    id = COALESCE(id, ?),
                    created_at = COALESCE(
                        created_at,
                        '2026-09-15T10:00:00+00:00'
                    ),
                    closed_at = COALESCE(
                        closed_at,
                        '2026-09-15T10:05:00+00:00'
                    )
                WHERE rowid=?
                """,
                (index, rowid),
            )


def _plan(
    *,
    raw_amount,
    available,
    reserve,
    risk_distance,
    known_edge,
    full_edge=None,
    cost_complete=False,
):
    return {
        "capital": {
            "entry_amount_usdt": raw_amount,
            "available_usdt": available,
            "safe_quote_reserve_usd": reserve,
            "kelly_fraction": 1.0,
        },
        "expected": {
            "known_net_edge_fraction": (
                known_edge
            ),
            "full_net_edge_fraction": (
                full_edge
            ),
        },
        "cost_model": {
            "cost_complete": (
                cost_complete
            ),
        },
        "market_statistics": {
            "risk_log_distance": (
                risk_distance
            ),
        },
    }


def test_edge_cannot_expand_exit_capacity(
    tmp_path,
):
    # Empty outcome DB => safely blocked.
    plan = _plan(
        raw_amount=9000,
        available=10000,
        reserve=2000,
        risk_distance=0.4,
        known_edge=9.0,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        db_path=str(
            tmp_path / "missing.db"
        ),
    )

    assert (
        result["entry_amount_usdt"]
        == 0.0
    )

    assert (
        "GAP_RISK_UNOBSERVED"
        in result["blockers"]
    )


def test_current_db_calibration_is_data_derived():
    plan = _plan(
        raw_amount=9000,
        available=10000,
        reserve=2000,
        risk_distance=0.4,
        known_edge=9.0,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
    )

    if result["gap_multiplier"] is None:
        assert (
            result["entry_amount_usdt"]
            == 0.0
        )
        return

    expected_cap = (
        2000
        * math.exp(-0.4)
        / result["gap_multiplier"]
    )

    assert (
        result["entry_amount_usdt"]
        <= expected_cap + 1e-9
    )

    assert (
        result["entry_amount_usdt"]
        <= 2000
    )

    assert (
        result["kelly_diagnostic_only"]
        is True
    )


def test_incomplete_cost_does_not_equal_zero():
    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=0.25,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
    )

    assert (
        result[
            "empirical_cost_uncertainty_fraction"
        ]
        is not None
        or result["entry_amount_usdt"] == 0.0
    )


def test_entry_plan_uses_observed_move_and_edge_without_fixed_percentages(tmp_path):
    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=0.1,
        full_edge=0.1,
        cost_complete=True,
    )
    plan["entry"] = {"price": 2.0}
    plan["statistics"] = {
        "prices": [2.0, 2.0 * math.exp(0.03), 2.0],
        "log_returns": [0.02, -0.03],
    }

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        db_path=str(tmp_path / "missing.db"),
    )

    anchor = 2.0 * math.exp(0.03)
    assert result["entry_zone_low"] == pytest.approx(anchor * math.exp(-0.03))
    assert result["entry_zone_high"] == pytest.approx(anchor)
    assert result["preferred_entry"] == pytest.approx(anchor * math.exp(-0.015))
    assert result["chase_limit"] == pytest.approx(anchor * math.exp(0.03))
    # The derived zone is valid, but the plan's remaining calibration
    # blockers still prevent immediate PAPER admission.
    assert result["immediate_entry_allowed"] is False


def _timing_plan(*, price, history, edge=0.1, trade_type="NORMAL", gate=None):
    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=edge,
        full_edge=edge,
        cost_complete=True,
    )
    plan["paper_eligible"] = True
    plan["entry"] = {"price": price}
    plan["statistics"] = {
        "prices": [*history, price],
    }
    if trade_type == "VUR_KAC":
        plan["vur_kac_entry"] = {"enforced": True, "ready": bool(gate)}
    return plan


def test_price_above_derived_chase_limit_is_blocked():
    plan = _timing_plan(price=3.0, history=[1.0, 1.1])
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["chase_limit"] == pytest.approx(1.1 * 1.1)
    assert result["chase_limit"] < 3.0
    assert result["entry_amount_usdt"] == 0.0
    assert result["immediate_entry_allowed"] is False
    assert "ENTRY_ABOVE_CHASE_LIMIT" in result["blockers"]
    assert _paper_entry_timing_reason(result) == "ENTRY_ABOVE_CHASE_LIMIT"


def test_price_inside_derived_zone_is_timing_eligible():
    plan = _timing_plan(price=1.01, history=[0.99, 1.0])
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["entry_zone_low"] <= 1.01 <= result["chase_limit"]
    assert result["immediate_entry_allowed"] is True
    assert _paper_entry_timing_reason(result) is None


def test_price_below_entry_zone_with_positive_size_is_watch_only():
    plan = _timing_plan(price=0.95, history=[0.99, 1.0])
    plan["capital"]["liquidity_capacity_source"] = "VERIFIED_LP_PROTECTION"
    plan["market_context"] = {"opportunity": {"state": "HOT"}}
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["entry_amount_usdt"] > 0
    assert result["immediate_entry_allowed"] is False
    assert _paper_entry_timing_reason(result) == "ENTRY_TIMING_NOT_READY"


def test_vur_kac_without_flow_readiness_is_not_immediate():
    plan = _timing_plan(price=1.01, history=[0.99, 1.0], trade_type="VUR_KAC", gate=False)
    plan["capital"]["liquidity_capacity_source"] = "VERIFIED_LP_PROTECTION"
    plan["market_context"] = {"opportunity": {"state": "HOT"}}
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["entry_amount_usdt"] > 0
    assert result["immediate_entry_allowed"] is False
    assert _paper_entry_timing_reason(result) == "ENTRY_TIMING_NOT_READY"


def test_vur_kac_with_continuation_and_flow_readiness_is_immediate():
    plan = _timing_plan(price=1.01, history=[0.99, 1.0], trade_type="VUR_KAC", gate=True)
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["immediate_entry_allowed"] is True


def test_negative_edge_or_hard_risk_keeps_zero_entry():
    plan = _timing_plan(price=1.01, history=[0.99, 1.0], edge=-0.01)
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["entry_amount_usdt"] == 0.0
    assert "NET_EDGE_NOT_POSITIVE" in result["blockers"]
    plan["hard_block"] = True
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["entry_amount_usdt"] == 0.0


def test_unverified_lp_bootstrap_stays_blocked_when_timing_ready(tmp_path):
    plan = _timing_plan(price=1.01, history=[0.99, 1.0])
    plan["capital"].update({
        "liquidity_capacity_source": "EMPIRICAL_RESERVE_FLOOR",
        "reserve_observation_count": 2,
        "observed_min_quote_reserve_usd": 5000,
    })
    plan["market_context"] = {
        "opportunity": {"state": "HOT"},
    }
    result = calculate_paper_position_size(
        mathematical_plan=plan,
        db_path=str(tmp_path / "missing.db"),
    )
    assert result["entry_amount_usdt"] == 0.0
    assert result["risk_amount_usdt"] == 0.0
    assert "LP_WITHDRAWAL_PROTECTION_UNVERIFIED" in result["blockers"]
    assert result.get("paper_calibration_bootstrap") is not True


def test_nonpositive_edge_zeros_sizing():
    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=0.0,
        full_edge=-0.01,
        cost_complete=True,
    )
    result = calculate_paper_position_size(mathematical_plan=plan)
    assert result["entry_amount_usdt"] == 0.0
    assert "NET_EDGE_NOT_POSITIVE" in result["blockers"]


def test_full_net_edge_used_when_complete():
    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=99.0,
        full_edge=0.15,
        cost_complete=True,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
    )

    if result["entry_amount_usdt"] > 0:
        assert (
            result["effective_edge_fraction"]
            == 0.15
        )


def test_negative_effective_edge_blocks():
    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=-0.01,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
    )

    assert (
        result["entry_amount_usdt"]
        == 0.0
    )



def test_archived_outcomes_feed_empirical_calibration(
    tmp_path,
):
    import json
    import sqlite3

    db_path = (
        tmp_path
        / "paper_archive_calibration.db"
    )

    db = sqlite3.connect(db_path)

    schema = """
        status TEXT,
        entry_price REAL,
        current_price REAL,
        entry_amount_usdt REAL,
        net_pnl REAL,
        mathematical_plan_json TEXT,
        math_state_json TEXT
    """

    db.execute(
        f"CREATE TABLE paper_trades ({schema})"
    )

    db.execute(
        f"""
        CREATE TABLE paper_trades_archive (
            {schema}
        )
        """
    )

    db.execute(
        """
        INSERT INTO paper_trades_archive (
            status,
            entry_price,
            current_price,
            entry_amount_usdt,
            net_pnl,
            mathematical_plan_json,
            math_state_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CLOSED",
            100.0,
            80.0,
            1000.0,
            -220.0,
            json.dumps(
                {
                    "entry": {
                        "band_low": 90.0,
                    }
                }
            ),
            json.dumps(
                {
                    "last_stop": 90.0,
                }
            ),
        ),
    )

    _stamp_outcome_fingerprints(db)
    db.commit()
    db.close()

    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=0.25,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        db_path=str(db_path),
    )

    assert math.isclose(
        result["gap_multiplier"],
        2.0,
    )

    assert math.isclose(
        result[
            "empirical_cost_uncertainty_fraction"
        ],
        0.02,
    )

    assert (
        "GAP_RISK_UNOBSERVED"
        not in result["blockers"]
    )

    assert (
        "COST_UNCERTAINTY_UNOBSERVED"
        not in result["blockers"]
    )

    assert result["entry_amount_usdt"] > 0



def test_closed_gross_net_accounting_drives_cost_uncertainty(
    tmp_path,
):
    import json
    import sqlite3

    db_path = (
        tmp_path
        / "gross_net_cost.db"
    )

    db = sqlite3.connect(db_path)

    db.execute(
        """
        CREATE TABLE paper_trades (
            status TEXT,
            entry_price REAL,
            current_price REAL,
            entry_amount_usdt REAL,
            net_pnl REAL,
            mathematical_plan_json TEXT,
            math_state_json TEXT,
            gross_pnl_usdt REAL,
            net_pnl_usdt REAL
        )
        """
    )

    db.execute(
        """
        INSERT INTO paper_trades (
            status,
            entry_price,
            current_price,
            entry_amount_usdt,
            net_pnl,
            mathematical_plan_json,
            math_state_json,
            gross_pnl_usdt,
            net_pnl_usdt
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CLOSED",
            100.0,
            300.0,
            100.0,
            50.0,
            json.dumps(
                {
                    "entry": {
                        "band_low": 90.0,
                    }
                }
            ),
            json.dumps({}),
            60.0,
            50.0,
        ),
    )

    _stamp_outcome_fingerprints(db)
    db.commit()
    db.close()

    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=0.25,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        db_path=str(db_path),
    )

    assert math.isclose(
        result[
            "empirical_cost_uncertainty_fraction"
        ],
        0.10,
    )



def test_gap_calibration_uses_worst_observed_tail(
    tmp_path,
):
    import json
    import sqlite3

    db_path = (
        tmp_path
        / "median_gap.db"
    )

    db = sqlite3.connect(db_path)

    db.execute(
        """
        CREATE TABLE paper_trades (
            status TEXT,
            entry_price REAL,
            current_price REAL,
            entry_amount_usdt REAL,
            net_pnl REAL,
            mathematical_plan_json TEXT,
            math_state_json TEXT
        )
        """
    )

    samples = (
        (100.0, 80.0, 90.0),
        (100.0, 80.0, 95.0),
        (100.0, 1.0, 99.0),
    )

    for entry, current, stop in samples:
        amount = 100.0

        mark_pnl = (
            amount
            * (
                current / entry
                - 1.0
            )
        )

        db.execute(
            """
            INSERT INTO paper_trades (
                status,
                entry_price,
                current_price,
                entry_amount_usdt,
                net_pnl,
                mathematical_plan_json,
                math_state_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CLOSED",
                entry,
                current,
                amount,
                mark_pnl,
                json.dumps(
                    {
                        "entry": {
                            "band_low": stop,
                        }
                    }
                ),
                json.dumps({}),
            ),
        )

    _stamp_outcome_fingerprints(db)
    db.commit()
    db.close()

    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=0.25,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        db_path=str(db_path),
    )

    assert math.isclose(
        result["gap_multiplier"],
        99.0,
    )



def test_zero_cost_rows_do_not_dilute_observed_cost_median(
    tmp_path,
):
    import json
    import sqlite3

    db_path = (
        tmp_path
        / "positive_cost_median.db"
    )

    db = sqlite3.connect(db_path)

    db.execute(
        """
        CREATE TABLE paper_trades (
            status TEXT,
            entry_price REAL,
            current_price REAL,
            entry_amount_usdt REAL,
            net_pnl REAL,
            mathematical_plan_json TEXT,
            math_state_json TEXT,
            gross_pnl_usdt REAL,
            net_pnl_usdt REAL
        )
        """
    )

    samples = (
        (-20.0, -20.0),
        (-20.0, -21.0),
        (-20.0, -23.0),
    )

    for gross, net in samples:
        db.execute(
            """
            INSERT INTO paper_trades (
                status,
                entry_price,
                current_price,
                entry_amount_usdt,
                net_pnl,
                mathematical_plan_json,
                math_state_json,
                gross_pnl_usdt,
                net_pnl_usdt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CLOSED",
                100.0,
                80.0,
                100.0,
                net,
                json.dumps(
                    {
                        "entry": {
                            "band_low": 90.0,
                        }
                    }
                ),
                json.dumps({}),
                gross,
                net,
            ),
        )

    _stamp_outcome_fingerprints(db)
    db.commit()
    db.close()

    plan = _plan(
        raw_amount=1000,
        available=10000,
        reserve=5000,
        risk_distance=0.2,
        known_edge=0.25,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        db_path=str(db_path),
    )

    assert math.isclose(
        result[
            "empirical_cost_uncertainty_fraction"
        ],
        0.02,
    )

    assert (
        result["cost_samples"]
        == 2
    )



def test_tail_gap_cannot_expand_original_stop_risk_budget(
    tmp_path,
):
    import json
    import sqlite3

    db_path = (
        tmp_path
        / "tail_risk_budget.db"
    )

    db = sqlite3.connect(
        db_path
    )

    db.execute(
        """
        CREATE TABLE paper_trades (
            status TEXT,
            entry_price REAL,
            current_price REAL,
            entry_amount_usdt REAL,
            net_pnl REAL,
            mathematical_plan_json TEXT,
            math_state_json TEXT
        )
        """
    )

    db.execute(
        """
        INSERT INTO paper_trades(
            status,
            entry_price,
            current_price,
            entry_amount_usdt,
            net_pnl,
            mathematical_plan_json,
            math_state_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CLOSED",
            100.0,
            1.0,
            100.0,
            -99.0,
            json.dumps(
                {
                    "entry": {
                        "band_low": 90.0,
                    }
                }
            ),
            json.dumps({}),
        ),
    )

    _stamp_outcome_fingerprints(db)
    db.commit()
    db.close()

    plan = _plan(
        raw_amount=1000.0,
        available=1000.0,
        reserve=1_000_000.0,
        risk_distance=0.2,
        known_edge=0.25,
        full_edge=0.25,
        cost_complete=True,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        available_capital_usdt=1000.0,
        db_path=str(
            db_path
        ),
    )

    original_stop_budget = (
        1000.0
        * (
            1.0
            - math.exp(-0.2)
        )
    )

    assert math.isclose(
        result["gap_multiplier"],
        9.9,
    )

    assert math.isclose(
        result["tail_loss_fraction"],
        1.0,
    )

    assert (
        result["entry_amount_usdt"]
        <= original_stop_budget
        + 1e-9
    )

    assert (
        result["risk_amount_usdt"]
        <= original_stop_budget
        + 1e-9
    )

    assert math.isclose(
        result[
            "stop_risk_budget_usdt"
        ],
        original_stop_budget / MAX_OPEN_PAPER_POSITIONS,
    )


def test_positive_float_dust_is_blocked_by_accounting_precision(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.risk.paper_position_sizing."
        "_empirical_outcome_calibration",
        lambda *args, **kwargs: {
            "ready": True,
            "reason": (
                "EMPIRICAL_OUTCOME_CALIBRATION"
            ),
            "gap_multiplier": 1.0,
            "gap_median": 1.0,
            "gap_statistic": "TEST",
            "cost_uncertainty_fraction": 0.0,
            "account_risk_budget_usdt": 100.0,
            "account_risk_statistic": "TEST",
            "gap_samples": 1,
            "cost_samples": 1,
            "account_risk_samples": 1,
        },
    )

    plan = _plan(
        raw_amount=1000.0,
        available=10000.0,
        reserve=1e-14,
        risk_distance=0.2,
        known_edge=0.25,
        full_edge=0.25,
        cost_complete=True,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        available_capital_usdt=10000.0,
    )

    assert (
        result["entry_amount_usdt"]
        == 0.0
    )

    assert (
        "ENTRY_AMOUNT_BELOW_ACCOUNTING_PRECISION"
        in result["blockers"]
    )



def test_id51_sub_quantum_micro_notional_is_blocked(
    monkeypatch,
):
    available = 9237.512079329967
    reserve = 5.634779807892627e-11
    risk_distance = 0.08124114491030021
    target_amount = 1.5615460017212325e-12

    accounting_quantum = (
        available
        - math.nextafter(
            available,
            -math.inf,
        )
    )

    assert target_amount < accounting_quantum

    # This reproduces the original bug: subtraction rounds
    # down by one float step even though the requested debit
    # itself is smaller than that representable step.
    assert (
        available - target_amount
        != available
    )

    gap_multiplier = (
        reserve
        * math.exp(-risk_distance)
        / target_amount
    )

    monkeypatch.setattr(
        "app.risk.paper_position_sizing."
        "_empirical_outcome_calibration",
        lambda *args, **kwargs: {
            "ready": True,
            "reason": (
                "EMPIRICAL_OUTCOME_CALIBRATION"
            ),
            "gap_multiplier": gap_multiplier,
            "gap_median": gap_multiplier,
            "gap_statistic": "ID51_REGRESSION",
            "cost_uncertainty_fraction": 0.0,
            "account_risk_budget_usdt": 100.0,
            "account_risk_statistic": "TEST",
            "gap_samples": 1,
            "cost_samples": 1,
            "account_risk_samples": 1,
        },
    )

    plan = _plan(
        raw_amount=1000.0,
        available=available,
        reserve=reserve,
        risk_distance=risk_distance,
        known_edge=0.6724150276335858,
        full_edge=None,
        cost_complete=False,
    )

    result = calculate_paper_position_size(
        mathematical_plan=plan,
        available_capital_usdt=available,
    )

    assert result["entry_amount_usdt"] == 0.0

    assert (
        "ENTRY_AMOUNT_BELOW_ACCOUNTING_PRECISION"
        in result["blockers"]
    )



def test_legacy_float_dust_does_not_poison_calibration(
    tmp_path,
):
    import json
    import sqlite3

    from app.risk.paper_position_sizing import (
        _empirical_outcome_calibration,
    )

    db_path = tmp_path / "dust_calibration.db"
    db = sqlite3.connect(db_path)

    db.execute(
        """
        CREATE TABLE paper_trades (
            status TEXT,
            entry_price REAL,
            current_price REAL,
            exit_price REAL,
            entry_amount_usdt REAL,
            net_pnl REAL,
            net_pnl_usdt REAL,
            gross_pnl_usdt REAL,
            mathematical_plan_json TEXT,
            math_state_json TEXT
        )
        """
    )

    plan = json.dumps({
        "entry": {
            "band_low": 90.0,
        }
    })

    state = json.dumps({})

    samples = (
        (
            1.0e-26,
            -1.0e-27,
        ),
        (
            100.0,
            -20.0,
        ),
    )

    for amount, net_pnl in samples:
        db.execute(
            """
            INSERT INTO paper_trades (
                status,
                entry_price,
                current_price,
                exit_price,
                entry_amount_usdt,
                net_pnl,
                net_pnl_usdt,
                gross_pnl_usdt,
                mathematical_plan_json,
                math_state_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CLOSED",
                100.0,
                80.0,
                80.0,
                amount,
                net_pnl,
                net_pnl,
                net_pnl,
                plan,
                state,
            ),
        )

    _stamp_outcome_fingerprints(db)
    db.commit()
    db.close()

    result = _empirical_outcome_calibration(
        str(db_path)
    )

    assert result["gap_samples"] == 1
    assert result["account_risk_samples"] == 1
    assert result["account_risk_budget_usdt"] == 20.0


def test_known_modeled_cost_is_not_charged_twice_in_uncertainty(
    tmp_path,
):
    import json
    import sqlite3

    db_path = tmp_path / "known_cost_residual.db"
    db = sqlite3.connect(db_path)

    db.execute(
        """
        CREATE TABLE paper_trades (
            status TEXT,
            entry_price REAL,
            current_price REAL,
            entry_amount_usdt REAL,
            net_pnl REAL,
            mathematical_plan_json TEXT,
            math_state_json TEXT,
            gross_pnl_usdt REAL,
            net_pnl_usdt REAL
        )
        """
    )

    plan = {
        "entry": {"band_low": 90.0},
        "cost_model": {
            "sell_retention_known": 0.99,
            "sell_gas_usd": 0.0,
        },
    }

    db.execute(
        """
        INSERT INTO paper_trades (
            status,
            entry_price,
            current_price,
            entry_amount_usdt,
            net_pnl,
            mathematical_plan_json,
            math_state_json,
            gross_pnl_usdt,
            net_pnl_usdt
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CLOSED",
            100.0,
            80.0,
            100.0,
            -22.0,
            json.dumps(plan),
            json.dumps({}),
            -20.0,
            -22.0,
        ),
    )

    _stamp_outcome_fingerprints(db)
    db.commit()
    db.close()

    from app.risk.paper_position_sizing import (
        _empirical_outcome_calibration,
    )

    result = _empirical_outcome_calibration(str(db_path))

    # Gross exit proceeds are $80, so 1% modeled sell retention costs
    # $0.80, not $1.00 of entry notional. The observed $2.00 spread
    # therefore leaves $1.20 / $100 = 1.2% residual uncertainty.
    assert math.isclose(
        result["cost_uncertainty_fraction"],
        0.012,
        abs_tol=1e-12,
    )
    assert result["cost_samples"] == 1
