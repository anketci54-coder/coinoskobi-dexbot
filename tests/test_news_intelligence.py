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


def test_duplicate_same_source_is_one_conservative_origin():
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


def test_social_sources_without_provenance_do_not_fake_corroboration():
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

    assert row["independent_source_count"] == 1
    assert len(row["sources"]) == 2
    assert row["confidence"] == 0.55


def test_distinct_social_origin_keys_can_corroborate():
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

    store.observe(
        source_type="X", source_id="account-a", origin_key="origin-a", **common
    )
    row = store.observe(
        source_type="DISCORD", source_id="server-b", origin_key="origin-b", **common
    )

    assert row["independent_source_count"] == 2
    assert row["confidence"] == 0.60


def test_low_trust_second_source_does_not_reduce_existing_confidence():
    store = NewsEvidenceStore()
    common = dict(
        event_type="LISTING",
        text="Spot listing opens tomorrow",
        published_at=1000,
        observed_at=1010,
    )
    first = store.observe(
        source_type="OFFICIAL_EXCHANGE",
        source_id="exchange",
        source_trust=0.70,
        official=True,
        **common,
    )
    second = store.observe(
        source_type="WEB",
        source_id="low-trust-copy",
        source_trust=0.10,
        **common,
    )
    assert second["confidence"] >= first["confidence"]


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


def test_stale_news_is_unknown_evidence():
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

    assert row["state"] == "UNKNOWN"
    assert row["freshness"] == "STALE"
    assert row["trade_signal"] is False


def test_snapshot_zero_returns_empty_and_status_has_no_authority():
    store = NewsEvidenceStore()
    store.observe(
        source_type="WEB",
        source_id="source",
        event_type="LISTING",
        text="Listing event",
        published_at=1000,
        observed_at=1001,
        source_trust=0.5,
    )
    assert store.snapshot(limit=0) == []
    status = store.status()
    for key in (
        "trade_signal", "decision_authority", "paper_authority",
        "live_authority", "wallet_authority", "signing_authority",
        "execution_authority",
    ):
        assert status[key] is False


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
