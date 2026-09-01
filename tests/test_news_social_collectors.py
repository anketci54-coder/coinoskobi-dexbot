import requests

from app.dex.news_social_collectors import (
    DiscordCollector,
    TelegramCollector,
    XCollector,
)
from app.dex.news_source_adapters import (
    TelegramNewsAdapter,
    XNewsAdapter,
)


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self._payload = payload
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_missing_credentials_make_no_network_calls():
    session = FakeSession(FakeResponse({}))

    telegram = TelegramCollector(session=session)
    discord = DiscordCollector(session=session)
    x = XCollector(session=session)

    assert telegram.fetch_updates()["state"] == "UNAVAILABLE"
    assert discord.fetch_channel("123")["state"] == "UNAVAILABLE"
    assert x.search_recent("airdrop")["state"] == "UNAVAILABLE"
    assert session.calls == []


def test_telegram_error_redacts_bot_token():
    token = "secret-telegram-token"
    error = requests.HTTPError(
        f"403 for https://api.telegram.org/bot{token}/getUpdates"
    )
    collector = TelegramCollector(
        bot_token=token,
        session=FakeSession(FakeResponse(error=error)),
    )

    result = collector.fetch_updates()

    assert result["state"] == "FETCH_ERROR"
    assert token not in (result["error"] or "")
    assert "[REDACTED]" in result["error"]


def test_invalid_timestamps_are_rejected_not_freshened():
    telegram = TelegramCollector(
        bot_token="t",
        session=FakeSession(
            FakeResponse(
                {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 1,
                            "channel_post": {
                                "message_id": 10,
                                "date": 0,
                                "text": "Airdrop announced",
                                "chat": {"id": -1},
                            },
                        }
                    ],
                }
            )
        ),
    )
    discord = DiscordCollector(
        bot_token="d",
        session=FakeSession(
            FakeResponse(
                [
                    {
                        "id": "1",
                        "content": "IDO announced",
                        "timestamp": "not-a-timestamp",
                        "author": {"id": "author", "verified": True},
                    }
                ]
            )
        ),
    )

    assert telegram.fetch_updates()["messages"] == []
    assert discord.fetch_channel("123")["messages"] == []


def test_discord_author_verified_does_not_become_news_verified():
    collector = DiscordCollector(
        bot_token="d",
        session=FakeSession(
            FakeResponse(
                [
                    {
                        "id": "1",
                        "content": "Listing announced",
                        "timestamp": "2026-09-01T18:00:00Z",
                        "author": {"id": "author", "verified": True},
                    }
                ]
            )
        ),
    )

    message = collector.fetch_channel("123")["messages"][0]
    assert message["verified"] is False


def test_telegram_forward_origin_survives_adapter():
    collector = TelegramCollector(
        bot_token="t",
        session=FakeSession(
            FakeResponse(
                {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 1,
                            "channel_post": {
                                "message_id": 10,
                                "date": 1788285600,
                                "text": "TGE announced",
                                "chat": {"id": -1},
                                "forward_origin": {
                                    "type": "channel",
                                    "chat": {"id": -99},
                                    "message_id": 77,
                                },
                            },
                        }
                    ],
                }
            )
        ),
    )

    message = collector.fetch_updates()["messages"][0]
    assert message["origin_key"] == "telegram:channel:-99:77"
    normalized = TelegramNewsAdapter().normalize(message)
    assert normalized["origin_key"] == message["origin_key"]


def test_x_repost_origin_survives_adapter():
    collector = XCollector(
        bearer_token="x",
        session=FakeSession(
            FakeResponse(
                {
                    "data": [
                        {
                            "id": "200",
                            "author_id": "10",
                            "text": "RT listing announcement",
                            "created_at": "2026-09-01T18:00:00Z",
                            "public_metrics": {},
                            "referenced_tweets": [
                                {"type": "retweeted", "id": "100"}
                            ],
                        }
                    ],
                    "meta": {},
                }
            )
        ),
    )

    message = collector.search_recent("listing")["messages"][0]
    assert message["origin_key"] == "x:retweeted:100"
    normalized = XNewsAdapter().normalize(message)
    assert normalized["origin_key"] == message["origin_key"]
