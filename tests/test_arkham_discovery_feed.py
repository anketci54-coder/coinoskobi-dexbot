import sqlite3

from app.dex.arkham_discovery_feed import (
    fetch_official_updates,
    ingest_official_updates,
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


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


def test_normalizes_only_bsc_candidates_and_deduplicates():
    address = _addr(1)
    rows = normalize_arkham_update_candidates(
        {
            "updates": [
                {"chain": "bsc", "address": address, "tagName": "Trader"},
                {"chainType": "BNB", "addressValue": address, "label": "Smart"},
                {"chain": "ethereum", "address": _addr(2)},
            ]
        }
    )
    assert rows == [
        {
            "chain": "bsc",
            "address": address,
            "metadata": {"tagName": "Trader"},
        }
    ]


def test_fetch_uses_official_endpoint_and_has_zero_authority(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "configured")
    captured = {}

    def getter(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _Response({"updates": [{"chain": "bsc", "address": _addr(3)}]})

    out = fetch_official_updates(
        "ADDRESS_TAG_UPDATES",
        params={"cursor": "abc"},
        getter=getter,
    )
    assert captured["url"].endswith("/intelligence/address_tags/updates")
    assert captured["kwargs"]["params"] == {"cursor": "abc"}
    assert out["available"] is True
    assert out["success_authority"] is False
    assert out["trade_authority"] is False
    assert out["execution_authority"] is False


def test_missing_key_makes_no_network_call(monkeypatch):
    monkeypatch.delenv("ARKHAM_API_KEY", raising=False)
    called = False

    def getter(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be called")

    out = fetch_official_updates("ADDRESS_UPDATES", getter=getter)
    assert out == {
        "available": False,
        "reason": "ARKHAM_NOT_CONFIGURED",
        "updates": [],
    }
    assert called is False


def test_official_update_ingest_is_observed_only(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    address = _addr(4)

    out = ingest_official_updates(
        path,
        {
            "available": True,
            "kind": "ADDRESS_TAG_UPDATES",
            "updates": [{"chain": "bsc", "address": address, "tag": "Trader"}],
        },
        source_key="address-tags:cursor-1",
        observed_at=100.0,
    )
    assert out["state"] == "READY"
    assert out["accepted"] == 1
    assert out["candidate_state"] == "OBSERVED"
    assert out["success_authority"] is False

    db = sqlite3.connect(path)
    evidence = db.execute(
        "SELECT source,candidate_state FROM wallet_discovery_source_evidence"
    ).fetchone()
    successes = db.execute("SELECT COUNT(*) FROM wallet_success_score").fetchone()[0]
    db.close()
    assert evidence == ("ARKHAM_ADDRESS_TAG_UPDATE", "OBSERVED")
    assert successes == 0


def test_provider_failure_does_not_mutate_db(tmp_path):
    path = tmp_path / "paper.db"
    _db(path)
    out = ingest_official_updates(
        path,
        {"available": False, "reason": "ARKHAM_HTTP_429", "updates": []},
        source_key="failed",
    )
    assert out["state"] == "PROVIDER_UNAVAILABLE"
    db = sqlite3.connect(path)
    registry_count = db.execute("SELECT COUNT(*) FROM wallet_discovery_registry").fetchone()[0]
    db.close()
    assert registry_count == 0
