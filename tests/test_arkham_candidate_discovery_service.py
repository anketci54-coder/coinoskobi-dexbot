import sqlite3

from app.dex.arkham_candidate_discovery_service import ArkhamCandidateDiscoveryService


def _addr(index: int) -> str:
    return "0x" + f"{index:040x}"


def _db(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE seed(id INTEGER PRIMARY KEY)")
    db.commit()
    db.close()


def test_successful_feeds_ingest_observed_candidates_and_advance_cursor(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    calls = []

    def fetcher(*, feed, since):
        calls.append((feed, since))
        index = 1 if feed == "ADDRESS_TAG_UPDATES" else 2
        return {
            "available": True,
            "feed": feed,
            "candidates": [{"chain": "bsc", "address": _addr(index)}],
            "fetched_at": 1000.0 + index,
        }

    service = ArkhamCandidateDiscoveryService(
        path,
        fetcher=fetcher,
        bootstrap_lookback_seconds=60,
    )
    out = service.run_cycle()

    assert out["state"] == "READY"
    assert out["feeds_succeeded"] == 2
    assert out["candidates_accepted"] == 2
    assert out["success_authority"] is False
    assert out["execution_authority"] is False

    db = sqlite3.connect(path)
    rows = db.execute(
        "SELECT source,candidate_state FROM wallet_discovery_source_evidence ORDER BY source"
    ).fetchall()
    cursors = db.execute(
        "SELECT feed,last_success_at,last_provider_state FROM wallet_discovery_feed_state ORDER BY feed"
    ).fetchall()
    success_table = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='wallet_success_score'"
    ).fetchone()
    db.close()

    assert rows == [
        ("ARKHAM_ADDRESS_TAG_UPDATE", "OBSERVED"),
        ("ARKHAM_ADDRESS_UPDATE", "OBSERVED"),
    ]
    assert cursors == [
        ("ADDRESS_TAG_UPDATES", 1001.0, "READY"),
        ("ADDRESS_UPDATES", 1002.0, "READY"),
    ]
    assert success_table is None
    assert len(calls) == 2


def test_provider_failure_does_not_advance_last_success_cursor(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    attempts = {"ADDRESS_TAG_UPDATES": 0, "ADDRESS_UPDATES": 0}

    def fetcher(*, feed, since):
        attempts[feed] += 1
        if feed == "ADDRESS_TAG_UPDATES" and attempts[feed] == 2:
            return {"available": False, "reason": "ARKHAM_HTTP_429", "candidates": []}
        return {
            "available": True,
            "candidates": [],
            "fetched_at": 1000.0 if attempts[feed] == 1 else 2000.0,
        }

    service = ArkhamCandidateDiscoveryService(path, fetcher=fetcher)
    first = service.run_cycle()
    assert first["state"] == "READY"
    second = service.run_cycle()
    assert second["state"] == "PARTIAL"

    db = sqlite3.connect(path)
    tag = db.execute(
        "SELECT last_success_at,last_provider_state FROM wallet_discovery_feed_state WHERE feed='ADDRESS_TAG_UPDATES'"
    ).fetchone()
    addr = db.execute(
        "SELECT last_success_at,last_provider_state FROM wallet_discovery_feed_state WHERE feed='ADDRESS_UPDATES'"
    ).fetchone()
    db.close()

    assert tag == (1000.0, "ARKHAM_HTTP_429")
    assert addr == (2000.0, "READY")


def test_previous_success_uses_overlap_cursor(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    seen = []

    def fetcher(*, feed, since):
        seen.append((feed, since))
        return {"available": True, "candidates": [], "fetched_at": 1000.0}

    service = ArkhamCandidateDiscoveryService(path, fetcher=fetcher)
    service.run_cycle()
    seen.clear()
    service.run_cycle()

    assert seen == [
        ("ADDRESS_TAG_UPDATES", 970.0),
        ("ADDRESS_UPDATES", 970.0),
    ]


def test_non_dict_provider_result_is_fail_soft(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    service = ArkhamCandidateDiscoveryService(path, fetcher=lambda **kwargs: None)

    out = service.run_cycle()

    assert out["state"] == "PROVIDER_UNAVAILABLE"
    assert out["provider_failures"] == 2
