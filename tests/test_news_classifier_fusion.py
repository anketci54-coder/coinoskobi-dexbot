from app.dex.news_classifier import classify_news_event
from app.dex.news_signal_fusion import fuse_news_signals


def event(event_type, confidence=0.9, state="CONFIRMED", token="bsc:0xabc"):
    return {
        "event_type": event_type,
        "confidence": confidence,
        "state": state,
        "freshness": "FRESH",
        "token_id": token,
    }


def test_classifies_airdrop_ido_ico_tge():
    assert classify_news_event("Official airdrop claim window opens tomorrow")["event_type"] == "AIRDROP"
    assert classify_news_event("Our IDO launches on the launchpad")["event_type"] == "IDO"
    assert classify_news_event("ICO token sale is now open")["event_type"] == "ICO"
    assert classify_news_event("TGE scheduled for Friday")["event_type"] == "TGE"


def test_negative_security_event_has_no_authority():
    out = classify_news_event("Protocol exploit detected and funds drained")
    assert out["event_type"] == "EXPLOIT"
    assert out["trade_signal"] is False
    assert out["execution_authority"] is False


def test_fusion_positive_is_advisory_only():
    out = fuse_news_signals([event("LISTING"), event("TGE")], token_id="bsc:0xabc")
    assert out["state"] == "READY"
    assert out["direction"] == "POSITIVE"
    assert out["advisory_only"] is True
    assert out["trade_signal"] is False
    assert out["decision_authority"] is False
    assert out["execution_authority"] is False


def test_conflicting_credible_news_becomes_mixed():
    out = fuse_news_signals([event("LISTING"), event("EXPLOIT")])
    assert out["state"] == "MIXED"
    assert out["direction"] == "MIXED"


def test_rumor_cannot_create_ready_signal():
    out = fuse_news_signals([event("RUMOR", confidence=0.35, state="RUMOR")])
    assert out["state"] == "UNVERIFIED"
    assert out["direction"] == "NEUTRAL"


def test_stale_and_other_token_are_ignored():
    stale = event("LISTING")
    stale["freshness"] = "STALE"
    other = event("LISTING", token="bsc:0xdef")
    out = fuse_news_signals([stale, other], token_id="bsc:0xabc")
    assert out["state"] == "UNKNOWN"
    assert out["event_count"] == 0


def test_fusion_is_bounded():
    rows = [event("LISTING") for _ in range(100)]
    out = fuse_news_signals(rows, max_events=7)
    assert out["event_count"] == 7
