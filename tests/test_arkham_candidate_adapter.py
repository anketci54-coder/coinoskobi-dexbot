import sqlite3

from app.dex.arkham_candidate_intake import run_arkham_candidate_intake
from app.dex.arkham_candidate_provider import normalize_address_tag_updates


def _addr(n: int) -> str:
    return "0x" + f"{n:040x}"


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


def test_normalizer_keeps_only_bsc_trader_signals():
    payload = {
        "updates": [
            {"address": _addr(1), "chain": "bsc", "tag": "High PnL Trader"},
            {"address": _addr(2), "chain": "bnb", "tag": "Smart Money"},
            {"address": _addr(3), "chain": "bsc", "tag": "Exchange Deposit"},
            {"address": _addr(4), "chain": "eth", "tag": "Whale Trader"},
        ]
    }
    out = normalize_address_tag_updates(payload)
    assert [row["address"] for row in out["candidates"]] == [_addr(1), _addr(2)]
    assert out["irrelevant"] == 1
    assert out["rejected"] == 1
    assert out["success_authority"] is False
    assert out["trade_authority"] is False


def test_intake_writes_observed_evidence_never_success(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)

    def fetcher(**_):
        return {
            "available": True,
            "fetched_at": 100.0,
            "candidates": [
                {"chain": "bsc", "address": _addr(11), "metadata": {"arkham_tag": "Trader"}}
            ],
        }

    out = run_arkham_candidate_intake(path, fetcher=fetcher)
    assert out["state"] == "READY"
    assert out["accepted"] == 1
    assert out["candidate_state"] == "OBSERVED"
    assert out["success_authority"] is False

    db = sqlite3.connect(path)
    evidence = db.execute(
        "SELECT source,candidate_state FROM wallet_discovery_source_evidence"
    ).fetchone()
    success = db.execute("SELECT COUNT(*) FROM wallet_success_score").fetchone()[0]
    db.close()
    assert evidence == ("ARKHAM_ADDRESS_TAG_UPDATE", "OBSERVED")
    assert success == 0


def test_provider_failure_does_not_touch_db(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)

    def fetcher(**_):
        return {"available": False, "reason": "ARKHAM_HTTP_429", "candidates": []}

    out = run_arkham_candidate_intake(path, fetcher=fetcher)
    assert out["state"] == "PROVIDER_UNAVAILABLE"
    assert out["accepted"] == 0

    db = sqlite3.connect(path)
    tables = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='wallet_discovery_source_evidence'"
    ).fetchone()[0]
    db.close()
    assert tables == 0


def test_normalizer_is_bounded_and_deduplicates():
    address = _addr(21)
    payload = [
        {"address": address, "chain": "bsc", "tag": "Trader"},
        {"address": address, "chain": "bsc", "tag": "Whale Trader"},
        {"address": _addr(22), "chain": "bsc", "tag": "Trader"},
    ]
    out = normalize_address_tag_updates(payload, limit=1)
    assert out["candidate_count"] == 1
    assert out["candidates"][0]["address"] == address
