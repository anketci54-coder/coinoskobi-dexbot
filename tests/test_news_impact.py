from app.api.news_impact import classify_and_forecast, forecast_news_event


def test_hack_is_high_risk_negative_without_trade_authority():
    out = forecast_news_event({
        "event_type": "HACK",
        "text": "protocol hacked",
        "confidence": 0.9,
        "freshness": "FRESH",
        "independent_source_count": 2,
        "token_id": "0xabc",
        "chain": "bsc",
    })
    assert out["direction"] == "NEGATIVE"
    assert out["risk"] == "HIGH"
    assert out["confidence_label"] == "HIGH"
    assert out["trade_signal"] is False
    assert out["decision_authority"] is False


def test_single_social_rumor_is_capped_low():
    out = forecast_news_event({
        "event_type": "RUMOR",
        "text": "rumor",
        "confidence": 0.95,
        "freshness": "FRESH",
        "independent_source_count": 1,
    })
    assert out["confidence"] <= 0.35
    assert out["confidence_label"] in {"LOW", "INSUFFICIENT"}


def test_regulatory_sanction_is_negative():
    out = forecast_news_event({
        "event_type": "REGULATORY",
        "text": "government announces sanctions and restrictions",
        "confidence": 0.8,
        "freshness": "FRESH",
        "independent_source_count": 2,
    })
    assert out["direction"] == "NEGATIVE"


def test_airdrop_classifier_forecast_is_not_trade_signal():
    out = classify_and_forecast("Official project announces an airdrop claim window")
    assert out["state"] == "READY"
    assert out["event_type"] == "AIRDROP"
    assert out["trade_signal"] is False
