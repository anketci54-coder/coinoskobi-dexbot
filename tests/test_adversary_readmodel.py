from app.dex.adversary_readmodel import (
    AdversaryReadModel,
    hot_path_contract,
)


def test_store_and_read():
    r = AdversaryReadModel(10)

    r.put(
        "bsc:0xabc",
        {
            "adversary_risk_bucket": "LOW_RISK",
            "mev_risk": "LOW",
        },
    )

    out = r.get("bsc:0xabc")

    assert out["state"] == "READY"
    assert out["payload"]["adversary_risk_bucket"] == "LOW_RISK"


def test_missing_unknown():
    r = AdversaryReadModel(10)
    assert r.get("bsc:missing")["state"] == "UNKNOWN"


def test_stale_safe():
    r = AdversaryReadModel(10)
    r.put("bsc:0xabc", {"risk": "LOW"})

    assert r.get(
        "bsc:0xabc",
        freshness="STALE",
    )["state"] == "STALE"


def test_bounded_eviction():
    r = AdversaryReadModel(2)

    r.put("bsc:1", {"x": 1})
    r.put("bsc:2", {"x": 2})
    r.put("bsc:3", {"x": 3})

    assert r.size == 2
    assert r.get("bsc:1")["state"] == "UNKNOWN"
    assert r.get("bsc:2")["state"] == "READY"
    assert r.get("bsc:3")["state"] == "READY"


def test_update_does_not_grow():
    r = AdversaryReadModel(2)

    r.put("bsc:1", {"x": 1})
    r.put("bsc:1", {"x": 2})

    assert r.size == 1
    assert r.get("bsc:1")["payload"]["x"] == 2


def test_hot_path_forbidden_operations():
    c = hot_path_contract()

    assert c["precomputed_readmodel_only"] is True
    assert c["bounded_cache"] is True
    assert c["deep_transaction_trace"] is False
    assert c["graph_expansion"] is False
    assert c["raw_event_join"] is False
    assert c["heavy_actor_aggregation"] is False
    assert c["ai_inference"] is False
    assert c["external_fetch"] is False
    assert c["provider_call"] is False


def test_authority_zero():
    c = hot_path_contract()

    assert c["decision_authority"] is False
    assert c["paper_authority"] is False
    assert c["live_authority"] is False
    assert c["wallet_authority"] is False
    assert c["execution_authority"] is False
