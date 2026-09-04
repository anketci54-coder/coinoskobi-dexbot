from app.api.wallet_intelligence_feed import MAX_TRACKED_WALLETS, score_wallet_candidate, select_top_wallets


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
