from app.dex.news_collector_runtime import NewsCollectorRuntime
from app.dex.news_intelligence import NewsEvidenceStore


def test_telegram_ingestion_classifies_and_records_airdrop():
    store = NewsEvidenceStore()
    runtime = NewsCollectorRuntime(store=store)
    result = runtime.ingest("TELEGRAM", [{
        "channel_id": "official-project",
        "text": "Airdrop claim window is now open",
        "published_at": 1000,
        "token_id": "0xabc",
        "source_trust": 0.8,
        "official": True,
    }])
    assert result["accepted"] == 1
    rows = store.snapshot(token_id="0xabc")
    assert rows[0]["event_type"] == "AIRDROP"
    assert rows[0]["trade_signal"] is False


def test_unknown_text_is_rejected_without_fabricating_event():
    store = NewsEvidenceStore()
    runtime = NewsCollectorRuntime(store=store)
    result = runtime.ingest("X", [{
        "account_id": "account",
        "text": "hello world",
        "published_at": 1000,
        "token_id": "0xabc",
        "source_trust": 0.5,
    }])
    assert result["accepted"] == 0
    assert result["rejected"] == 1
    assert store.snapshot(token_id="0xabc") == []


def test_batch_is_bounded():
    store = NewsEvidenceStore(max_events=20)
    runtime = NewsCollectorRuntime(store=store, max_batch=2)
    messages = [
        {
            "source_id": f"feed-{i}",
            "text": f"Token sale announcement {i}",
            "published_at": 1000 + i,
            "token_id": f"0x{i}",
            "source_trust": 0.6,
        }
        for i in range(5)
    ]
    result = runtime.ingest("RSS", messages)
    assert result["accepted"] == 2
    assert store.status()["count"] == 2


def test_invalid_source_is_safe_and_authority_free():
    runtime = NewsCollectorRuntime(store=NewsEvidenceStore())
    result = runtime.ingest("UNKNOWN", [])
    assert result["state"] == "INVALID_SOURCE"
    assert result["decision_authority"] is False
    assert result["execution_authority"] is False
