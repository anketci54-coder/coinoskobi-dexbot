import sqlite3

from app.dex import wallet_candidate_discovery as discovery
from app.dex.wallet_candidate_discovery import ingest_wallet_candidates


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


def test_external_candidate_is_observed_without_success_authority(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)

    out = ingest_wallet_candidates(
        path,
        [{"chain": "bsc", "address": "0xABC", "rank": 412}],
        source="ARKHAM_TOP_TRADERS",
        source_key="top-traders:2026-09-05",
        observed_at=100.0,
    )

    assert out["state"] == "READY"
    assert out["accepted"] == 1
    assert out["candidate_state"] == "OBSERVED"
    assert out["success_authority"] is False
    assert out["trade_authority"] is False

    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    evidence = db.execute(
        "SELECT * FROM wallet_discovery_source_evidence"
    ).fetchone()
    registry = db.execute(
        "SELECT * FROM wallet_discovery_registry"
    ).fetchone()
    success_count = db.execute(
        "SELECT COUNT(*) FROM wallet_success_score"
    ).fetchone()[0]
    db.close()

    assert evidence["wallet_uid"] == "bsc:0xabc"
    assert evidence["candidate_state"] == "OBSERVED"
    assert evidence["external_rank"] == 412
    assert evidence["source"] == "ARKHAM_TOP_TRADERS"
    assert registry["discovery_source"] == "ARKHAM_TOP_TRADERS"
    assert success_count == 0


def test_second_source_does_not_destroy_existing_registry_provenance(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    db = sqlite3.connect(path)
    db.execute(
        """
        INSERT INTO wallet_discovery_registry VALUES(
            'bsc:0xabc','bsc','0xabc',1,1,
            'TRANSACTION_FROM_ONLY','FRESH','ACTIVE'
        )
        """
    )
    db.commit()
    db.close()

    ingest_wallet_candidates(
        path,
        [{"chain": "bsc", "address": "0xABC", "rank": 9}],
        source="ARKHAM_TRADER_TAG",
        source_key="tag:trader",
        observed_at=200.0,
    )

    db = sqlite3.connect(path)
    source = db.execute(
        "SELECT discovery_source FROM wallet_discovery_registry WHERE wallet_uid='bsc:0xabc'"
    ).fetchone()[0]
    evidence_count = db.execute(
        "SELECT COUNT(*) FROM wallet_discovery_source_evidence WHERE wallet_uid='bsc:0xabc'"
    ).fetchone()[0]
    last_seen = db.execute(
        "SELECT last_seen_at FROM wallet_discovery_registry WHERE wallet_uid='bsc:0xabc'"
    ).fetchone()[0]
    db.close()

    assert source == "TRANSACTION_FROM_ONLY"
    assert evidence_count == 1
    assert last_seen == 200.0


def test_same_source_key_refreshes_evidence_in_place(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)

    ingest_wallet_candidates(
        path,
        [{"chain": "bsc", "address": "0xabc", "rank": 44}],
        source="ARKHAM_TOP_TRADERS",
        source_key="top-traders",
        observed_at=100.0,
    )
    ingest_wallet_candidates(
        path,
        [{"chain": "bsc", "address": "0xabc", "rank": 12}],
        source="ARKHAM_TOP_TRADERS",
        source_key="top-traders",
        observed_at=300.0,
    )

    db = sqlite3.connect(path)
    row = db.execute(
        "SELECT external_rank,first_seen_at,last_seen_at,active FROM wallet_discovery_source_evidence"
    ).fetchone()
    db.close()

    assert row == (12, 100.0, 300.0, 1)


def test_candidate_pool_is_bounded_by_distinct_wallet(tmp_path, monkeypatch):
    path = tmp_path / "paper.db"
    _db(path)
    monkeypatch.setattr(discovery, "MAX_DISCOVERY_CANDIDATES", 2)

    ingest_wallet_candidates(
        path,
        [
            {"chain": "bsc", "address": "0x001"},
            {"chain": "bsc", "address": "0x002"},
            {"chain": "bsc", "address": "0x003"},
        ],
        source="ARKHAM_ADDRESS_TAG_UPDATE",
        source_key="tags:update",
        observed_at=100.0,
    )

    db = sqlite3.connect(path)
    active = db.execute(
        """
        SELECT wallet_uid FROM wallet_discovery_source_evidence
        WHERE active=1 ORDER BY wallet_uid
        """
    ).fetchall()
    inactive = db.execute(
        "SELECT COUNT(*) FROM wallet_discovery_source_evidence WHERE active=0"
    ).fetchone()[0]
    success_count = db.execute(
        "SELECT COUNT(*) FROM wallet_success_score"
    ).fetchone()[0]
    db.close()

    assert len(active) == 2
    assert inactive == 1
    assert success_count == 0


def test_invalid_rows_are_rejected_without_registry_pollution(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)

    out = ingest_wallet_candidates(
        path,
        [None, {}, {"chain": "bsc", "address": ""}],
        source="ARKHAM_TRADER_TAG",
        source_key="tag:trader",
        observed_at=100.0,
    )

    assert out["accepted"] == 0
    assert out["rejected"] == 3
    db = sqlite3.connect(path)
    registry_count = db.execute(
        "SELECT COUNT(*) FROM wallet_discovery_registry"
    ).fetchone()[0]
    evidence_count = db.execute(
        "SELECT COUNT(*) FROM wallet_discovery_source_evidence"
    ).fetchone()[0]
    db.close()
    assert registry_count == 0
    assert evidence_count == 0
