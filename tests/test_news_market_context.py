from app.dex.news_intelligence import NewsEvidenceStore
from app.pipeline.news_market_context import bind_news_market_context


TOKEN = "0xabc"


def test_missing_news_store_is_explicit_unknown():
    result = bind_news_market_context({}, {"token": TOKEN}, None)
    news = result["news_intelligence"]
    assert news["state"] == "UNKNOWN"
    assert news["trade_signal"] is False
    assert news["execution_authority"] is False


def test_fresh_news_is_bound_to_candidate_token_only():
    store = NewsEvidenceStore(fresh_seconds=3600)
    store.observe(
        source_type="OFFICIAL_PROJECT",
        source_id="project",
        event_type="AIRDROP",
        text="Official airdrop announced",
        published_at=1000,
        observed_at=1001,
        token_id=TOKEN,
        source_trust=0.9,
        verified=True,
        official=True,
    )
    store.observe(
        source_type="OFFICIAL_PROJECT",
        source_id="other",
        event_type="EXPLOIT",
        text="Other token exploit",
        published_at=1000,
        observed_at=1001,
        token_id="0xdef",
        source_trust=0.9,
        verified=True,
        official=True,
    )

    result = bind_news_market_context({}, {"token": TOKEN}, store)
    news = result["news_intelligence"]

    assert news["event_count"] == 1
    assert news["fresh_event_types"] == ["AIRDROP"]
    assert news["trade_signal"] is False
    assert news["decision_authority"] is False
    assert news["wallet_authority"] is False
    assert news["signing_authority"] is False
    assert news["execution_authority"] is False


def test_missing_token_identity_does_not_cross_bind_news():
    store = NewsEvidenceStore()
    result = bind_news_market_context({}, {"pool": "0xpool"}, store)
    assert result["news_intelligence"]["state"] == "UNKNOWN"
    assert result["news_intelligence"]["token_id"] is None
