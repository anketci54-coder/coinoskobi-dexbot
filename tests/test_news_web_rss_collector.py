from app.dex.news_web_rss_collector import NewsWebRSSCollector


class FakeResponse:
    def __init__(self, content=b"", encoding="utf-8"):
        self.content = content
        self.encoding = encoding

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_private_and_local_urls_are_rejected_without_network():
    session = FakeSession(FakeResponse())
    collector = NewsWebRSSCollector(session=session)

    for url in (
        "http://127.0.0.1/feed",
        "http://10.0.0.1/feed",
        "http://169.254.1.1/feed",
        "http://localhost/feed",
        "http://example.localhost/feed",
        "http://[::1]/feed",
    ):
        assert collector.fetch_rss(url)["state"] == "INVALID_URL"

    assert session.calls == []


def test_url_credentials_are_rejected():
    session = FakeSession(FakeResponse())
    collector = NewsWebRSSCollector(session=session)

    result = collector.fetch_rss("https://user:pass@example.com/feed")

    assert result["state"] == "INVALID_URL"
    assert session.calls == []


def test_rss_missing_timestamp_is_not_freshened():
    rss = b"""<?xml version='1.0'?>
    <rss><channel><item>
      <title>Airdrop announced</title>
      <description>Claim opens soon</description>
      <link>https://example.com/a</link>
    </item></channel></rss>
    """
    collector = NewsWebRSSCollector(
        session=FakeSession(FakeResponse(rss))
    )

    result = collector.fetch_rss("https://example.com/feed")

    assert result["state"] == "READY"
    assert result["messages"] == []


def test_rss_valid_timestamp_is_preserved():
    rss = b"""<?xml version='1.0'?>
    <rss><channel><item>
      <title>TGE announced</title>
      <description>Token generation event</description>
      <pubDate>Mon, 01 Sep 2026 18:00:00 GMT</pubDate>
    </item></channel></rss>
    """
    collector = NewsWebRSSCollector(
        session=FakeSession(FakeResponse(rss))
    )

    result = collector.fetch_rss("https://example.com/feed")

    assert result["state"] == "READY"
    assert len(result["messages"]) == 1
    assert result["messages"][0]["published_at"] > 0


def test_web_text_requires_explicit_published_at_before_network():
    session = FakeSession(FakeResponse(b"Listing announced"))
    collector = NewsWebRSSCollector(session=session)

    result = collector.fetch_web_text("https://example.com/news")

    assert result["state"] == "MISSING_PUBLISHED_AT"
    assert session.calls == []


def test_web_text_valid_timestamp_and_public_url_are_accepted():
    session = FakeSession(FakeResponse(b"Listing announced"))
    collector = NewsWebRSSCollector(session=session)

    result = collector.fetch_web_text(
        "https://example.com/news",
        published_at=1788285600,
    )

    assert result["state"] == "READY"
    assert len(result["messages"]) == 1
    assert result["messages"][0]["published_at"] == 1788285600.0
    assert len(session.calls) == 1


def test_oversized_body_is_rejected():
    session = FakeSession(FakeResponse(b"x" * 2048))
    collector = NewsWebRSSCollector(
        session=session,
        max_bytes=1024,
    )

    result = collector.fetch_rss("https://example.com/feed")

    assert result["state"] == "TOO_LARGE"
    assert result["messages"] == []


def test_authority_is_always_false():
    collector = NewsWebRSSCollector(
        session=FakeSession(FakeResponse(b""))
    )
    result = collector.fetch_rss("http://127.0.0.1/feed")

    for key in (
        "trade_signal",
        "decision_authority",
        "paper_authority",
        "live_authority",
        "wallet_authority",
        "signing_authority",
        "execution_authority",
    ):
        assert result[key] is False
