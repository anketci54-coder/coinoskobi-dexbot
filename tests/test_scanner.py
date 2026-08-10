import app.scanner.gecko_scanner as scanner_module
from app.scanner.gecko_scanner import GeckoScanner


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "data": [
                {
                    "attributes": {
                        "address": "0xpool",
                        "name": "Example / WBNB",
                        "base_token_price_usd": "0.001",
                        "fdv_usd": "100000",
                        "market_cap_usd": "90000",
                        "reserve_in_usd": "15000",
                        "volume_usd": {
                            "h24": "5000",
                        },
                        "transactions": {
                            "h24": {
                                "buys": 25,
                            },
                        },
                        "pool_created_at": "2026-08-10T00:00:00Z",
                    },
                    "relationships": {
                        "base_token": {
                            "data": {
                                "id": "bsc_0xtoken",
                            },
                        },
                        "quote_token": {
                            "data": {
                                "id": "bsc_0xwbnb",
                            },
                        },
                        "dex": {
                            "data": {
                                "id": "pancakeswap_v2",
                            },
                        },
                    },
                },
            ],
        }


def test_scanner_parses_geckoterminal_response(monkeypatch):
    def fake_get(url, headers, timeout):
        assert "new_pools" in url
        assert headers["Accept"]
        assert timeout > 0
        return FakeResponse()

    monkeypatch.setattr(
        scanner_module.requests,
        "get",
        fake_get,
    )

    rows = GeckoScanner().scan()

    assert len(rows) == 1

    row = rows[0]

    assert row["pool"] == "0xpool"
    assert row["base_token"] == "bsc_0xtoken"
    assert row["quote_token"] == "bsc_0xwbnb"
    assert row["dex"] == "pancakeswap_v2"

    assert row["price_usd"] == 0.001
    assert row["fdv"] == 100000
    assert row["market_cap"] == 90000
    assert row["liquidity"] == 15000
    assert row["volume_24h"] == 5000
    assert row["buys_24h"] == 25
