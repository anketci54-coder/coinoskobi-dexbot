import sqlite3

from app.api import panel
from app.paper.schema import ensure_paper_schema


def test_panel_uses_active_paper_run_boundary(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"

    db = sqlite3.connect(db_path)
    ensure_paper_schema(db)

    for pnl in (-500.0, 250.0):
        db.execute(
            """
            INSERT INTO paper_trades (
                status,
                paper_account_version,
                net_pnl_usdt,
                roi
            )
            VALUES (
                'CLOSED',
                'PAPER_10K_V2',
                ?,
                0
            )
            """,
            (pnl,),
        )

    boundary = db.execute(
        "SELECT MAX(id) FROM paper_trades"
    ).fetchone()[0]

    db.execute(
        """
        INSERT INTO paper_runs (
            run_key,
            started_at,
            starting_capital_usdt,
            start_trade_id,
            start_realization_id,
            start_candidate_id,
            status,
            metadata_json
        )
        VALUES (
            'TEST_10K_RUN',
            1,
            10000,
            ?,
            0,
            0,
            'ACTIVE',
            '{}'
        )
        """,
        (boundary,),
    )

    db.execute(
        """
        INSERT INTO paper_trades (
            status,
            paper_account_version,
            net_pnl_usdt,
            roi
        )
        VALUES (
            'CLOSED',
            'PAPER_10K_V2',
            100,
            0.01
        )
        """
    )

    db.commit()
    db.close()

    monkeypatch.setattr(
        panel,
        "PAPER_DB",
        db_path,
    )

    assert (
        panel.panel_active_period_min_trade_id()
        == boundary + 1
    )

    assert (
        panel.panel_active_period_label()
        == "TEST_10K_RUN"
    )

    assert (
        panel.panel_starting_capital_usdt()
        == 10000.0
    )

    perf = panel.performance_payload(
        active_only=True
    )

    assert perf["closed"] == 1
    assert perf["net_total"] == 100.0

    rows = panel.paper_rows(
        active_only=True
    )

    assert len(rows) == 1
    assert rows[0]["id"] == boundary + 1
