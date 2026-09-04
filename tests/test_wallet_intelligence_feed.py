from app.api import wallet_intelligence_feed as feed
from app.api.wallet_intelligence_feed import (
    MAX_TRACKED_ASSETS_PER_WALLET,
    MAX_TRACKED_WALLETS,
    normalize_address_balances,
    score_wallet_candidate,
    select_top_wallets,
)


def test_wallet_score_uses_more_than_pnl():
    steady = {"address": "0x1", "trade_count": 80, "win_rate": 0.7, "roi": 1.2, "recency_score": 0.9, "consistency": 0.8}
    lucky = {"address": "0x2", "trade_count": 1, "win_rate": 1.0, "roi": 8.0, "recency_score": 1.0, "consistency": 0.1}
    assert score_wallet_candidate(steady) > score_wallet_candidate(lucky)


def test_select_top_wallets_excludes_exchange_and_contract():
    rows = [
        {"address": "0x1", "trade_count": 50, "win_rate": 0.6, "roi": 1, "recency_score": 1, "consistency": 0.7},
        {"address": "0x2", "trade_count": 100, "win_rate": 0.9, "roi": 3, "recency_score": 1, "consistency": 1, "is_exchange": True},
        {"address": "0x3", "trade_count": 100, "win_rate": 0.9, "roi": 3, "recency_score": 1, "consistency": 1, "is_contract": True},
    ]
    out = select_top_wallets(rows)
    assert [row["address"] for row in out] == ["0x1"]


def test_top_wallets_is_bounded_to_500():
    rows = [
        {"address": f"0x{i}", "trade_count": 50, "win_rate": 0.6, "roi": 1, "recency_score": 1, "consistency": 0.7}
        for i in range(700)
    ]
    assert len(select_top_wallets(rows, limit=9999)) == MAX_TRACKED_WALLETS


def test_normalize_address_balances_is_chain_aware_and_bounded():
    payload = {
        "balances": {
            "bsc": [
                {
                    "ethereumAddress": "0xABC",
                    "symbol": "AAA",
                    "name": "Alpha",
                    "balance": 5,
                    "usd": 50,
                    "price": 10,
                    "priceChange24hPercent": 2.5,
                    "quoteTime": "2026-09-04T00:00:00Z",
                },
                {
                    "id": "native-bnb",
                    "symbol": "BNB",
                    "balance": 2,
                    "usd": 1200,
                    "price": 600,
                },
                {"symbol": "BAD", "balance": -1, "usd": 10},
            ],
            "ethereum": [
                {"ethereumAddress": "0xDEF", "balance": 1, "usd": 9999},
            ],
        }
    }

    rows = normalize_address_balances(payload, chain="bsc", limit=2)

    assert len(rows) == 2
    assert rows[0]["token_id"] == "bsc:arkham:native-bnb"
    assert rows[0]["value_usd"] == 1200.0
    assert rows[1]["token_id"] == "bsc:0xabc"
    assert rows[1]["price_change_24h_pct"] == 2.5
    assert all(row["source"] == "ARKHAM" for row in rows)
    assert MAX_TRACKED_ASSETS_PER_WALLET == 128


def test_fetch_balances_for_address_uses_official_address_balance_endpoint(monkeypatch):
    calls = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "balances": {
                    "bsc": [
                        {
                            "ethereumAddress": "0xABC",
                            "symbol": "AAA",
                            "balance": 5,
                            "usd": 50,
                        }
                    ]
                },
                "totalBalance": {"bsc": 50},
            }

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setenv("ARKHAM_API_KEY", "test-key")
    monkeypatch.setattr(feed.requests, "get", fake_get)

    out = feed.fetch_balances_for_address("0xWallet", chain="bsc")

    assert out["available"] is True
    assert out["complete_snapshot"] is True
    assert out["total_value_usd"] == 50.0
    assert out["holdings"][0]["token_id"] == "bsc:0xabc"
    assert calls[0][0] == "https://api.arkm.com/balances/address/0xWallet"
    assert calls[0][1]["params"] == {"chains": "bsc"}
    assert calls[0][1]["headers"]["API-Key"] == "test-key"
    assert out["wallet_authority"] is False
    assert out["execution_authority"] is False


def test_fetch_balances_without_key_is_fail_soft(monkeypatch):
    monkeypatch.delenv("ARKHAM_API_KEY", raising=False)

    out = feed.fetch_balances_for_address("0xWallet")

    assert out == {
        "available": False,
        "reason": "ARKHAM_NOT_CONFIGURED",
        "holdings": [],
    }
