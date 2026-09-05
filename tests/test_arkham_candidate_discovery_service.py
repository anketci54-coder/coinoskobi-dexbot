import sqlite3

from app.dex.arkham_candidate_discovery_service import ArkhamCandidateDiscoveryService


def _addr(index: int) -> str:
    return "0x" + f"{index:040x}"


def _db(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE seed(id INTEGER PRIMARY KEY)")
    db.commit()
    db.close()


def test_address_feed_ingests_observed_candidates_and_advances_cursor(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    calls = []

    def fetcher(*, feed, since):
        calls.append((feed, since))
        return {
            "available": True,
            "feed": feed,
            "candidates": [{"chain": "bsc", "address": _addr(1)}],
            "fetched_at": 1001.0,
        }

    service = ArkhamCandidateDiscoveryService(
        path,
        fetcher=fetcher,
        bootstrap_lookback_seconds=60,
    )
    out = service.run_cycle()

    assert out["state"] == "READY"
    assert out["feeds_succeeded"] == 1
    assert out["candidates_accepted"] == 1
    assert out["active_feed"] == "ADDRESS_UPDATES"
    assert out["address_tag_feed_active"] is False
    assert out["success_authority"] is False
    assert out["execution_authority"] is False

    db = sqlite3.connect(path)
    rows = db.execute(
        "SELECT source,candidate_state FROM wallet_discovery_source_evidence"
    ).fetchall()
    cursors = db.execute(
        "SELECT feed,last_success_at,last_provider_state FROM wallet_discovery_feed_state"
    ).fetchall()
    success_table = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='wallet_success_score'"
    ).fetchone()
    db.close()

    assert rows == [("ARKHAM_ADDRESS_UPDATE", "OBSERVED")]
    assert cursors == [("ADDRESS_UPDATES", 1001.0, "READY")]
    assert success_table is None
    assert [feed for feed, _ in calls] == ["ADDRESS_UPDATES"]


def test_provider_failure_does_not_advance_last_success_cursor(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    attempts = 0

    def fetcher(*, feed, since):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            return {"available": False, "reason": "ARKHAM_HTTP_429", "candidates": []}
        return {
            "available": True,
            "candidates": [],
            "fetched_at": 1000.0,
        }

    service = ArkhamCandidateDiscoveryService(path, fetcher=fetcher)
    first = service.run_cycle()
    assert first["state"] == "READY"
    second = service.run_cycle()
    assert second["state"] == "PROVIDER_UNAVAILABLE"

    db = sqlite3.connect(path)
    address_feed = db.execute(
        "SELECT last_success_at,last_provider_state FROM wallet_discovery_feed_state WHERE feed='ADDRESS_UPDATES'"
    ).fetchone()
    tag_feed = db.execute(
        "SELECT 1 FROM wallet_discovery_feed_state WHERE feed='ADDRESS_TAG_UPDATES'"
    ).fetchone()
    db.close()

    assert address_feed == (1000.0, "ARKHAM_HTTP_429")
    assert tag_feed is None


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

    assert seen == [("ADDRESS_UPDATES", 970.0)]


def test_non_dict_provider_result_is_fail_soft(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    service = ArkhamCandidateDiscoveryService(path, fetcher=lambda **kwargs: None)

    out = service.run_cycle()

    assert out["state"] == "PROVIDER_UNAVAILABLE"
    assert out["provider_failures"] == 1


def test_status_explicitly_marks_tag_feed_inactive(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    status = ArkhamCandidateDiscoveryService(path).status()
    assert status["active_feed"] == "ADDRESS_UPDATES"
    assert status["address_tag_feed_active"] is False
