import sqlite3
from types import SimpleNamespace

import pytest

import app.api.panel as panel_module
from app.paper.schema import ensure_paper_schema


@pytest.fixture
def panel_db(tmp_path, monkeypatch):
    db_path = tmp_path / "panel_paper10k.db"

    conn = sqlite3.connect(db_path)
    ensure_paper_schema(conn)

    rows = [
        {
            "token": "0xlegacywin",
            "symbol": "LEGACY_WIN",
            "status": "CLOSED",
            "entry_price": 1.0,
            "current_price": 2.0,
            "highest_price": 2.0,
            "lowest_price": 1.0,
            "token_amount": 1.0,
            "net_pnl": 999.0,
            "roi": 1.0,
            "close_reason": "TAKE_PROFIT",
            "paper_account_version": None,
            "net_pnl_usdt": None,
        },
        {
            "token": "0xpaperwin",
            "symbol": "PAPER_WIN",
            "status": "CLOSED",
            "entry_price": 1.0,
            "current_price": 1.2,
            "highest_price": 1.2,
            "lowest_price": 1.0,
            "token_amount": 100.0,
            "net_pnl": 20.0,
            "roi": 0.20,
            "close_reason": "TAKE_PROFIT",
            "paper_account_version": "PAPER_10K_V2",
            "net_pnl_usdt": 20.0,
        },
        {
            "token": "0xpaperloss",
            "symbol": "PAPER_LOSS",
            "status": "CLOSED",
            "entry_price": 1.0,
            "current_price": 0.9,
            "highest_price": 1.0,
            "lowest_price": 0.9,
            "token_amount": 100.0,
            "net_pnl": -10.0,
            "roi": -0.10,
            "close_reason": "STOP_LOSS",
            "paper_account_version": "PAPER_10K_V2",
            "net_pnl_usdt": -10.0,
        },
        {
            "token": "0xpaperopen",
            "symbol": "PAPER_OPEN",
            "status": "OPEN",
            "entry_price": 1.0,
            "current_price": 1.0,
            "highest_price": 1.0,
            "lowest_price": 1.0,
            "token_amount": 100.0,
            "net_pnl": 0.0,
            "roi": 0.0,
            "close_reason": None,
            "paper_account_version": "PAPER_10K_V2",
            "net_pnl_usdt": 0.0,
        },
    ]

    for row in rows:
        columns = ",".join(row)
        placeholders = ",".join("?" for _ in row)

        conn.execute(
            f"""
            INSERT INTO paper_trades ({columns})
            VALUES ({placeholders})
            """,
            tuple(row.values()),
        )

    conn.commit()
    conn.close()

    monkeypatch.setattr(
        panel_module,
        "PAPER_DB",
        db_path,
    )

    return db_path


def test_status_counts_only_paper_10k_generation(panel_db):
    result = panel_module.status()

    assert result["total"] == 3
    assert result["new_generation"] == 3
    assert result["open_positions"] == 1
    assert result["closed_positions"] == 2


def test_performance_uses_paper_10k_usdt_accounting(panel_db):
    result = panel_module.performance()

    assert result["closed"] == 2
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["win_rate_pct"] == pytest.approx(50.0)
    assert result["avg_roi_pct"] == pytest.approx(5.0)
    assert result["net_total"] == pytest.approx(10.0)


def test_exits_use_only_paper_10k_usdt_accounting(panel_db):
    result = panel_module.exits()

    by_reason = {
        row["close_reason"]: row
        for row in result
    }

    assert set(by_reason) == {
        "TAKE_PROFIT",
        "STOP_LOSS",
    }

    take_profit = by_reason["TAKE_PROFIT"]
    assert take_profit["trades"] == 1
    assert take_profit["avg_roi_pct"] == pytest.approx(20.0)
    assert take_profit["net_total"] == pytest.approx(20.0)

    stop_loss = by_reason["STOP_LOSS"]
    assert stop_loss["trades"] == 1
    assert stop_loss["avg_roi_pct"] == pytest.approx(-10.0)
    assert stop_loss["net_total"] == pytest.approx(-10.0)

def test_runtime_candidate_snapshot_keeps_previous_cycle_while_scanner_runs():
    lines = [
        "08:55:00 [JOB] scanner",
        (
            "08:55:01 Candidate token=0xold "
            "pool=0xpoolold"
        ),
        "08:55:04 [JOB] paper_manager",
        "09:00:00 [JOB] scanner",
        (
            "09:00:01 Candidate token=0xpartial "
            "pool=0xpoolpartial"
        ),
    ]

    selected = (
        panel_module
        ._runtime_candidate_cycle_lines(
            lines
        )
    )

    assert selected == lines[1:3]
    assert "0xold" in selected[0]
    assert not any(
        "0xpartial" in line
        for line in selected
    )


def test_runtime_candidate_snapshot_switches_after_scanner_completes():
    lines = [
        "08:55:00 [JOB] scanner",
        (
            "08:55:01 Candidate token=0xold "
            "pool=0xpoolold"
        ),
        "08:55:04 [JOB] paper_manager",
        "09:00:00 [JOB] scanner",
        (
            "09:00:01 Candidate token=0xnew "
            "pool=0xpoolnew"
        ),
        "09:00:04 [JOB] paper_manager",
    ]

    selected = (
        panel_module
        ._runtime_candidate_cycle_lines(
            lines
        )
    )

    assert selected == lines[4:]
    assert "0xnew" in selected[0]


def test_runtime_candidate_snapshot_allows_true_zero_after_completed_scan():
    lines = [
        "08:55:00 [JOB] scanner",
        (
            "08:55:01 Candidate token=0xold "
            "pool=0xpoolold"
        ),
        "08:55:04 [JOB] paper_manager",
        "09:00:00 [JOB] scanner",
        "09:00:04 [JOB] paper_manager",
    ]

    selected = (
        panel_module
        ._runtime_candidate_cycle_lines(
            lines
        )
    )

    assert selected == lines[4:]
    assert not any(
        "Candidate token=" in line
        for line in selected
    )



def test_runtime_candidate_rows_preserves_complete_blocker_lists(
    monkeypatch,
):
    log = "\n".join([
        "2026-08-24T13:54:00+0300 [JOB] scanner",
        (
            "2026-08-24T13:54:03+0300 "
            "Candidate token=0xtoken "
            "pool=0xpool "
            "strategy=PAPER_BUY "
            "unified=PAPER_BUY_CANDIDATE "
            "paper=WATCH "
            "reason=PLAN_BLOCKED "
            "plan_blockers=['KNOWN_COMPONENT_EDGE_NOT_POSITIVE', "
            "'MATHEMATICAL_POSITION_SIZE_ZERO', "
            "'NO_VERIFIED_PERSISTENT_LIQUIDITY'] "
            "sizing_blockers=['EXIT_CAPACITY_UNKNOWN', "
            "'NET_EDGE_NOT_POSITIVE', "
            "'PLAN_AMOUNT_ZERO'] "
            "sizing_reason=MATHEMATICAL_POSITION_SIZE_ZERO "
            "entry_amount_usdt=0.0 "
            "hard_block=False "
            "evidence_coverage=100.0 "
            "coverage_confidence=100.0 "
            "sellability=SELLABILITY_OK"
        ),
        "2026-08-24T13:54:04+0300 [JOB] paper_manager",
    ])

    monkeypatch.setattr(
        panel_module,
        "runtime_cache_snapshot",
        lambda: {
            "by_pool": {
                "0xpool": {
                    "name": "TEST / WBNB",
                    "liquidity": 10000.0,
                    "volume_24h": 5000.0,
                    "fdv": 25000.0,
                    "price_usd": 0.001,
                },
            },
            "by_token": {},
        },
    )

    monkeypatch.setattr(
        panel_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=log,
        ),
    )

    rows = panel_module.runtime_candidate_rows()

    assert len(rows) == 1

    row = rows[0]

    assert row["reason"] == "PLAN_BLOCKED"

    assert row["plan_blockers"] == [
        "KNOWN_COMPONENT_EDGE_NOT_POSITIVE",
        "MATHEMATICAL_POSITION_SIZE_ZERO",
        "NO_VERIFIED_PERSISTENT_LIQUIDITY",
    ]

    assert row["sizing_blockers"] == [
        "EXIT_CAPACITY_UNKNOWN",
        "NET_EDGE_NOT_POSITIVE",
        "PLAN_AMOUNT_ZERO",
    ]

    assert (
        row["sizing_reason"]
        == "MATHEMATICAL_POSITION_SIZE_ZERO"
    )

    assert row["entry_amount_usdt"] == 0.0
    assert row["hard_block"] is False
    assert row["sellability"] == "SELLABILITY_OK"
