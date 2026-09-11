import sqlite3

from app.paper.schema import (
    PAPER_SCHEMA_VERSION,
    ensure_paper_schema,
)


REQUIRED_WALLET_TABLES = {
    "wallet_discovery_registry",
    "wallet_success_score",
    "wallet_outcome_evidence",
    "wallet_holding_snapshot",
    "wallet_holding_scan_state",
    "wallet_holding_change_evidence",
    "wallet_discovery_feed_state",
    "wallet_discovery_source_evidence",
    "whale_activity_snapshot",
}


def test_paper_schema_bootstraps_wallet_observation_tables(tmp_path):
    path = tmp_path / "paper.db"
    db = sqlite3.connect(path)

    first = ensure_paper_schema(db)
    second = ensure_paper_schema(db)

    tables = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    assert REQUIRED_WALLET_TABLES.issubset(tables)
    assert db.execute("PRAGMA user_version").fetchone()[0] == PAPER_SCHEMA_VERSION

    for result in (first, second):
        wallet = result["wallet_observation_schemas"]
        assert wallet["intelligence"]["state"] == "READY"
        assert wallet["discovery"]["state"] == "READY"
        assert wallet["holdings"]["state"] == "READY"

        assert wallet["intelligence"]["decision_authority"] is False
        assert wallet["intelligence"]["paper_authority"] is False
        assert wallet["intelligence"]["live_authority"] is False
        assert wallet["intelligence"]["wallet_authority"] is False
        assert wallet["intelligence"]["signing_authority"] is False
        assert wallet["intelligence"]["execution_authority"] is False

        assert wallet["discovery"]["decision_authority"] is False
        assert wallet["discovery"]["paper_authority"] is False
        assert wallet["discovery"]["live_authority"] is False
        assert wallet["discovery"]["wallet_authority"] is False
        assert wallet["discovery"]["signing_authority"] is False
        assert wallet["discovery"]["execution_authority"] is False

        assert wallet["holdings"]["decision_authority"] is False
        assert wallet["holdings"]["paper_authority"] is False
        assert wallet["holdings"]["live_authority"] is False
        assert wallet["holdings"]["wallet_authority"] is False
        assert wallet["holdings"]["signing_authority"] is False
        assert wallet["holdings"]["execution_authority"] is False

    db.close()
