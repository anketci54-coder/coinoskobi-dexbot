import math

from app.risk.paper_position_sizing import (
    calculate_paper_position_size,
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
        original_stop_budget,
    )
