from app.dex.whale_flow import analyze_whale_flow


def test_single_whale():
    r = analyze_whale_flow(1000, 800, 500, 100, 1)
    assert r["state"] == "CONCENTRATED"
    assert "SINGLE_WHALE_DOMINANCE" in r["tags"]


def test_multi_whale():
    r = analyze_whale_flow(1000, 300, 600, 200, 4)
    assert r["state"] == "DISTRIBUTED"
    assert "MULTI_WHALE_ACTIVITY" in r["tags"]


def test_net_inflow():
    r = analyze_whale_flow(1000, 300, 700, 100, 3)
    assert "WHALE_NET_INFLOW" in r["tags"]


def test_net_outflow():
    r = analyze_whale_flow(1000, 300, 100, 700, 3)
    assert "WHALE_NET_OUTFLOW" in r["tags"]


def test_cex_bridge_is_context():
    r = analyze_whale_flow(
        1000, 300, 400, 300, 3, cex_bridge=True
    )
    assert "CEX_BRIDGE_EVIDENCE" in r["tags"]
    assert r["trade_signal"] is False


def test_dust_noise():
    r = analyze_whale_flow(
        1000, 300, 400, 300, 3, dust_ratio=0.70
    )
    assert r["state"] == "NOISY"
    assert "DUST_NOISE" in r["tags"]


def test_stale_unknown():
    assert analyze_whale_flow(
        1000, 300, 400, 300, 3, freshness="STALE"
    )["state"] == "UNKNOWN"


def test_authority_zero():
    r = analyze_whale_flow(1000, 300, 400, 300, 3)
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
