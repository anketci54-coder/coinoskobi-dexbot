from app.dex.wallet_readmodel import WalletReadModel, hot_path_contract


def test_store_and_read():
    r = WalletReadModel(10)
    r.put("bsc:0xabc", {"risk": "LOW"})
    out = r.get("bsc:0xabc")
    assert out["state"] == "READY"
    assert out["payload"]["risk"] == "LOW"


def test_missing_unknown():
    r = WalletReadModel(10)
    assert r.get("bsc:0xmissing")["state"] == "UNKNOWN"


def test_stale_safe():
    r = WalletReadModel(10)
    r.put("bsc:0xabc", {"risk": "LOW"})
    assert r.get(
        "bsc:0xabc",
        freshness="STALE",
    )["state"] == "STALE"


def test_bounded_eviction():
    r = WalletReadModel(2)

    r.put("bsc:1", {"x": 1})
    r.put("bsc:2", {"x": 2})
    r.put("bsc:3", {"x": 3})

    assert r.size == 2
    assert r.get("bsc:1")["state"] == "UNKNOWN"
    assert r.get("bsc:3")["state"] == "READY"


def test_update_does_not_grow():
    r = WalletReadModel(2)

    r.put("bsc:1", {"x": 1})
    r.put("bsc:1", {"x": 2})

    assert r.size == 1
    assert r.get("bsc:1")["payload"]["x"] == 2


def test_hot_path_contract():
    c = hot_path_contract()

    assert c["raw_event_join"] is False
    assert c["graph_traversal"] is False
    assert c["heavy_wallet_aggregation"] is False
    assert c["precomputed_readmodel_only"] is True
    assert c["bounded_cache"] is True


def test_authority_zero():
    r = WalletReadModel(2)
    r.put("bsc:1", {"x": 1})
    out = r.get("bsc:1")
    c = hot_path_contract()

    assert out["decision_authority"] is False
    assert out["execution_authority"] is False
    assert c["decision_authority"] is False
    assert c["execution_authority"] is False
