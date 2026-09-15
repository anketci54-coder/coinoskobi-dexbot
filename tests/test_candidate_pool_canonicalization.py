from app.pipeline.normalizer import CandidateNormalizer


def test_gecko_bsc_strips_bsc_prefix_from_pool():
    pool = "0x00000000000000000000000000000000000000aa"
    token = "0x0000000000000000000000000000000000000001"
    quote = "0x0000000000000000000000000000000000000002"

    candidate = CandidateNormalizer.gecko_bsc({
        "pool": f"bsc_{pool}",
        "token": f"bsc_{token}",
        "quote_token": f"bsc_{quote}",
        "dex": "pancakeswap_v2",
        "provider": "geckoterminal",
        "liquidity": 50000.0,
        "volume_24h": 100000.0,
        "buys_24h": 20,
        "sells_24h": 10,
        "fdv": 1000000.0,
        "price_usd": 1.0,
    })

    assert candidate.pool == pool
    assert candidate.token == token
    assert candidate.quote_token == quote
