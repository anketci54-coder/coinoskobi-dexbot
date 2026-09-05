import sqlite3

from app.dex.arkham_candidate_adapter import (
    ingest_arkham_intelligence_updates,
    normalize_arkham_update_candidates,
)


def _addr(index: int) -> str:
    return "0x" + f"{index:040x}"


def _db(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE wallet_discovery_registry(
            wallet_uid TEXT PRIMARY KEY,
            chain TEXT,
            address TEXT,
            first_seen_at REAL,
            last_seen_at REAL,
            discovery_source TEXT,
            freshness_state TEXT,
            lifecycle_state TEXT
        );
        CREATE TABLE wallet_success_score(
            wallet_uid TEXT PRIMARY KEY,
            calculated_at REAL,
            sample_depth INTEGER,
            qualification_state TEXT
        );
        """
    )
    db.commit()
    db.close()


def test_trader_tag_update_becomes_observed_candidate_only(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    address = _addr(7)
    result = {
        "available": True,
        "kind": "ADDRESS_TAGS",
        "fetched_at": 123.0,
        "rows": [
            {
                "chain": "bsc",
                "address": address,
                "tag": {"name": "High PnL Trader"},
            }
        ],
    }

    out = ingest_arkham_intelligence_updates(
        path,
        result,
        source_key="address-tags:cursor-1",
    )

    assert out["accepted"] == 1
    assert out["candidate_state"] == "OBSERVED"
    assert out["success_authority"] is False
    assert out["trade_authority"] is False

    db = sqlite3.connect(path)
    evidence = db.execute(
        "SELECT source,candidate_state FROM wallet_discovery_source_evidence"
    ).fetchone()
    success = db.execute("SELECT COUNT(*) FROM wallet_success_score").fetchone()[0]
    db.close()
    assert evidence == ("ARKHAM_ADDRESS_TAG_UPDATE", "OBSERVED")
    assert success == 0


def test_normalizer_filters_non_bsc_non_trader_and_deduplicates():
    address = _addr(9)
    candidates, rejected = normalize_arkham_update_candidates(
        [
            {"chain": "bsc", "address": address, "label": "Smart Money Trader"},
            {"chain": "bsc", "address": address.upper().replace("0X", "0x"), "label": "Trader"},
            {"chain": "eth", "address": _addr(10), "label": "Trader"},
            {"chain": "bsc", "address": _addr(11), "label": "Exchange"},
            None,
        ]
    )
    assert len(candidates) == 1
    assert candidates[0]["address"].lower() == address
    assert rejected == 3


def test_provider_not_ready_does_not_touch_discovery_db(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    out = ingest_arkham_intelligence_updates(
        path,
        {"available": False, "kind": "ADDRESS_TAGS", "rows": []},
        source_key="address-tags:none",
    )
    assert out["state"] == "PROVIDER_NOT_READY"
    assert out["accepted"] == 0

    db = sqlite3.connect(path)
    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    db.close()
    assert "wallet_discovery_source_evidence" not in tables


def test_address_intelligence_feed_uses_observed_tag_source(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    address = _addr(12)
    out = ingest_arkham_intelligence_updates(
        path,
        {
            "available": True,
            "kind": "ADDRESSES",
            "fetched_at": 456.0,
            "rows": [{"chainType": "bsc", "address": address, "type": "Profitable Trader"}],
        },
        source_key="addresses:cursor-2",
    )
    assert out["accepted"] == 1
    db = sqlite3.connect(path)
    source = db.execute(
        "SELECT source FROM wallet_discovery_source_evidence"
    ).fetchone()[0]
    db.close()
    assert source == "ARKHAM_TRADER_TAG"
