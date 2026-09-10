from app.scanner.gecko_scanner import GeckoScanner


class Gecko429:
    status_code = 429

    def raise_for_status(self):
        raise RuntimeError("rate limited")


class DexResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "pairs": [
                {
                    "chainId": "bsc",
                    "pairAddress": "0xpool1",
                    "dexId": "pancakeswap",
                    "labels": ["v2"],
                    "baseToken": {
                        "address": "0xtoken1",
                        "symbol": "TOKEN1",
                    },
                    "quoteToken": {
                        "address": "0xquote1",
                        "symbol": "WBNB",
                    },
                    "priceUsd": "1.25",
                    "fdv": "1250000",
                    "marketCap": "1000000",
                    "liquidity": {"usd": "250000"},
                    "volume": {"h24": "750000"},
                    "txns": {"h24": {"buys": 321}},
                }
            ]
        }


def test_rate_limited_gecko_cools_down_and_falls_back_to_dexscreener(monkeypatch):
    calls = []
    sleeps = []

    def get(url, **kwargs):
        calls.append(url)
        if "geckoterminal" in url:
            return Gecko429()
        return DexResponse()

    monkeypatch.setattr(
        "app.scanner.gecko_scanner.requests.get",
        get,
    )
    monkeypatch.setattr(
        "app.scanner.gecko_scanner.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    monkeypatch.setattr(
        "app.scanner.gecko_scanner.persist_registered_followup_snapshots",
        lambda rows: None,
    )

    rows = GeckoScanner().pool_snapshots(["0xpool1"])

    assert len(rows) == 1
    assert rows[0]["pool"] == "0xpool1"
    assert rows[0]["provider"] == "dexscreener"
    assert rows[0]["dex"] == "pancakeswap_v2"
    assert rows[0]["price_usd"] == 1.25
    assert len([url for url in calls if "geckoterminal" in url]) == 3
    assert len([url for url in calls if "dexscreener" in url]) == 1
    assert sleeps == [2, 4]


def test_gecko_cooldown_skips_provider_on_next_cycle(monkeypatch):
    calls = []

    class DexOnlyResponse(DexResponse):
        pass

    def get(url, **kwargs):
        calls.append(url)
        if "geckoterminal" in url:
            return Gecko429()
        return DexOnlyResponse()

    monkeypatch.setattr(
        "app.scanner.gecko_scanner.requests.get",
        get,
    )
    monkeypatch.setattr(
        "app.scanner.gecko_scanner.time.sleep",
        lambda seconds: None,
    )
    monkeypatch.setattr(
        "app.scanner.gecko_scanner.persist_registered_followup_snapshots",
        lambda rows: None,
    )

    scanner = GeckoScanner()
    scanner.pool_snapshots(["0xpool1"])
    first_gecko_calls = len([url for url in calls if "geckoterminal" in url])

    scanner.pool_snapshots(["0xpool1"])
    second_gecko_calls = len([url for url in calls if "geckoterminal" in url])

    assert first_gecko_calls == 3
    assert second_gecko_calls == first_gecko_calls
