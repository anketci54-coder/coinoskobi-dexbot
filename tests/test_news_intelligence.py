from app.dex.news_intelligence import NewsEvidenceStore, normalize_source_event


def test_official_verified_airdrop_can_be_confirmed_without_trade_authority():
    store = NewsEvidenceStore()
    row = store.observe(
        source_type="OFFICIAL_PROJECT",
        source_id="project-alpha",
        event_type="AIRDROP",
        text="Airdrop claim opens tomorrow",
        published_at=1000,
        observed_at=1010,
        token_id="bsc:0xabc",
        chain="bsc",
        source_trust=0.65,
        official=True,
        verified=True,
    )

    assert row["state"] == "CONFIRMED"
    assert row["event_type"] == "AIRDROP"
    assert row["trade_signal"] is False
    assert row["decision_authority"] is False
    assert row["execution_authority"] is False


def test_telegram_discord_x_are_supported_source_boundaries():
    for source in ("TELEGRAM", "DISCORD", "X"):
        normalized = normalize_source_event(
            source,
            {
                "source_id": "channel",
                "event_type": "IDO",
                "text": "IDO announced",
                "published_at": 1000,
            },
        )
        assert normalized["source_type"] == source
        assert normalized["event_type"] == "IDO"


def test_duplicate_same_source_does_not_create_independent_confirmation():
    store = NewsEvidenceStore()
    kwargs = dict(
        source_type="TELEGRAM",
        source_id="channel-a",
        event_type="ICO",
        text="ICO starts Friday",
        published_at=1000,
        observed_at=1010,
        token_id="bsc:0xabc",
        source_trust=0.40,
    )

    first = store.observe(**kwargs)
    second = store.observe(**kwargs)

    assert first["independent_source_count"] == 1
    assert second["independent_source_count"] == 1
    assert len(store.snapshot()) == 1


def test_independent_sources_corroborate_same_normalized_event():
    store = NewsEvidenceStore()
    common = dict(
        event_type="TGE",
        text="Token generation event at 12 UTC",
        published_at=1000,
        observed_at=1010,
        token_id="bsc:0xabc",
        chain="bsc",
        source_trust=0.55,
    )

    store.observe(source_type="X", source_id="account-a", **common)
    row = store.observe(source_type="DISCORD", source_id="server-b", **common)

    assert row["independent_source_count"] == 2
    assert len(row["sources"]) == 2


def test_rumor_is_capped_and_never_promoted_to_confirmed():
    store = NewsEvidenceStore()
    row = store.observe(
        source_type="X",
        source_id="anonymous",
        event_type="RUMOR",
        text="Exchange listing maybe tomorrow",
        published_at=1000,
        observed_at=1010,
        source_trust=1.0,
        verified=True,
        official=True,
    )

    assert row["state"] == "RUMOR"
    assert row["confidence"] <= 0.35


def test_stale_news_degrades_to_stale_evidence():
    store = NewsEvidenceStore(fresh_seconds=60)
    row = store.observe(
        source_type="RSS",
        source_id="feed",
        event_type="PARTNERSHIP",
        text="Old partnership announcement",
        published_at=1000,
        observed_at=2000,
        source_trust=0.9,
        verified=True,
    )

    assert row["state"] == "STALE"
    assert row["freshness"] == "STALE"
    assert row["trade_signal"] is False


def test_store_is_bounded():
    store = NewsEvidenceStore(max_events=2)
    for idx in range(3):
        store.observe(
            source_type="WEB",
            source_id=f"source-{idx}",
            event_type="LISTING",
            text=f"Listing event {idx}",
            published_at=1000 + idx,
            observed_at=1001 + idx,
            source_trust=0.5,
        )

    assert store.status()["count"] == 2
    assert len(store.snapshot()) == 2
