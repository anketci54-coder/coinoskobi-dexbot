from app.dex.news_source_adapters import (
    DiscordNewsAdapter,
    RSSNewsAdapter,
    TelegramNewsAdapter,
    WebNewsAdapter,
    XNewsAdapter,
)


def _base(**extra):
    row = {
        "source_id": "source-1",
        "event_type": "AIRDROP",
        "text": "Project announces an airdrop",
        "published_at": 1000,
        "token_id": "bsc:0xabc",
        "chain": "bsc",
        "source_trust": 0.8,
        "verified": True,
        "official": True,
    }
    row.update(extra)
    return row


def test_telegram_adapter_preserves_channel_metadata():
    row = TelegramNewsAdapter().normalize(
        _base(message_id="11", channel_name="official-project")
    )
    assert row["source_type"] == "TELEGRAM"
    assert row["metadata"]["message_id"] == "11"
    assert row["metadata"]["channel_name"] == "official-project"


def test_discord_adapter_accepts_content_and_channel_id_aliases():
    row = DiscordNewsAdapter().normalize(
        {
            "channel_id": "discord-channel",
            "event_type": "IDO",
            "content": "IDO opens tomorrow",
            "created_at": 1000,
            "source_trust": 0.7,
        }
    )
    assert row["source_type"] == "DISCORD"
    assert row["source_id"] == "discord-channel"
    assert row["text"] == "IDO opens tomorrow"


def test_x_adapter_preserves_social_acceleration_metrics():
    row = XNewsAdapter().normalize(
        _base(
            event_type="SOCIAL_ACCELERATION",
            post_id="99",
            account_handle="project",
            repost_count=500,
            like_count=1000,
        )
    )
    assert row["source_type"] == "X"
    assert row["metadata"]["post_id"] == "99"
    assert row["metadata"]["repost_count"] == 500
    assert row["metadata"]["like_count"] == 1000


def test_web_and_rss_adapters_preserve_urls():
    web = WebNewsAdapter().normalize(_base(url="https://example.test/news"))
    rss = RSSNewsAdapter().normalize(
        _base(source_id=None, feed_id="feed-1", url="https://example.test/rss")
    )
    assert web["metadata"]["url"] == "https://example.test/news"
    assert rss["source_id"] == "feed-1"
    assert rss["metadata"]["url"] == "https://example.test/rss"


def test_adapters_do_not_create_authority_fields_themselves():
    row = XNewsAdapter().normalize(_base())
    assert "trade_signal" not in row
    assert "decision_authority" not in row
    assert "execution_authority" not in row
