import app.cache.gecko_cache as gecko_cache_module

from app.dex.market_quality import analyze_market_quality
from app.pipeline.intelligence_composition import RuntimeIntelligenceComposition
from app.pipeline.market_context import build_market_context
from app.pipeline.normalizer import CandidateNormalizer
from app.scanner.gecko_scanner import GeckoScanner


POOL = "0x0000000000000000000000000000000000000001"
TOKEN = "0x0000000000000000000000000000000000000002"
QUOTE = "0x0000000000000000000000000000000000000003"


class _RuntimeFeed:
    def __init__(self):
        self._events = {}

    def snapshot(self, pair, candidate=None):
        return {
            "state": "READY",
            "pair": pair,
            "market_intelligence": {
                "evidence_ready": True,
                "volume_usd": 25000.0,
                "liquidity_usd": 50000.0,
                "buys": 40,
            },
            "flow_intelligence": {
                "evidence_ready": False,
            },
        }


def test_gecko_parser_preserves_h24_sells():
    row = {
        "attributes": {
            "address": POOL,
            "base_token_price_usd": "1.25",
            "fdv_usd": "100000",
            "market_cap_usd": "90000",
            "reserve_in_usd": "50000",
            "volume_usd": {"h24": "25000"},
            "transactions": {
                "h24": {
                    "buys": 40,
                    "sells": 31,
                }
            },
            "pool_created_at": "2026-01-01T00:00:00Z",
        },
        "relationships": {
            "base_token": {"data": {"id": f"bsc_{TOKEN}"}},
            "quote_token": {"data": {"id": f"bsc_{QUOTE}"}},
            "dex": {"data": {"id": "pancakeswap_v2"}},
        },
    }

    candidate = GeckoScanner._row_to_candidate(row)

    assert candidate["buys_24h"] == 40
    assert candidate["sells_24h"] == 31


def test_dexscreener_parser_preserves_h24_sells():
    row = {
        "pairAddress": POOL,
        "baseToken": {"address": TOKEN, "symbol": "AAA"},
        "quoteToken": {"address": QUOTE, "symbol": "WBNB"},
        "dexId": "pancakeswap",
        "labels": ["v2"],
        "priceUsd": "1.25",
        "fdv": 100000,
        "marketCap": 90000,
        "liquidity": {"usd": 50000},
        "volume": {"h24": 25000},
        "txns": {"h24": {"buys": 40, "sells": 31}},
    }

    candidate = GeckoScanner._dex_row_to_candidate(row)

    assert candidate["buys_24h"] == 40
    assert candidate["sells_24h"] == 31


def test_normalizer_preserves_canonical_sells_h24():
    candidate = CandidateNormalizer.gecko_bsc({
        "pool": POOL,
        "base_token": TOKEN,
        "quote_token": QUOTE,
        "dex": "pancakeswap_v2",
        "liquidity_usd": 50000,
        "volume_h24_usd": 25000,
        "buys_h24": 40,
        "sells_h24": 31,
        "fdv_usd": 100000,
        "price_usd": 1.25,
    })

    assert candidate.buys_24h == 40
    assert candidate.sells_24h == 31
    assert candidate.to_dict()["sells_24h"] == 31


def test_cache_migrates_and_persists_sells(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gecko_cache_module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = gecko_cache_module.GeckoCache()

    try:
        cache.replace({
            "pool": POOL,
            "base_token": f"bsc_{TOKEN}",
            "quote_token": f"bsc_{QUOTE}",
            "name": "AAA / WBNB",
            "dex": "pancakeswap_v2",
            "liquidity": 50000,
            "volume_24h": 25000,
            "buys_24h": 40,
            "sells_24h": 31,
            "fdv": 100000,
            "price_usd": 1.25,
            "created_at": "2026-01-01T00:00:00Z",
            "market_cap": 90000,
            "source": "geckoterminal",
            "chain": "bsc",
        })

        cached = cache.all()[0]
        history = cache.history_for_pool(POOL)

        assert cached["sells_24h"] == 31
        assert history[-1]["sells_24h"] == 31
    finally:
        cache.db.close()


def test_market_context_binds_scanner_sells_without_wallet_guessing():
    context = build_market_context(
        {
            "pool": POOL,
            "token": TOKEN,
            "quote_token": QUOTE,
            "liquidity": 50000,
            "volume_24h": 25000,
            "buys_24h": 40,
            "sells_24h": 31,
        },
        runtime_feed=_RuntimeFeed(),
    )

    market = context["market_intelligence"]
    participation = context["origin_participation"]

    assert market["buys"] == 40
    assert market["sells"] == 31
    assert market["sell_count_source"] == "SCANNER_PROVIDER_24H"
    assert "buyers" not in market
    assert "sellers" not in market
    assert participation["state"] == "UNKNOWN"

    quality = RuntimeIntelligenceComposition().build(
        TOKEN,
        market_input=market,
    )["market_quality"]

    assert quality["transaction_evidence_ready"] is True
    assert quality["participant_evidence_ready"] is False
    assert quality["market_evidence_ready"] is False


def test_market_quality_still_requires_real_participant_evidence():
    result = analyze_market_quality(
        volume_usd=25000,
        liquidity_usd=50000,
        buys=40,
        sells=31,
        buyers=None,
        sellers=None,
    )

    assert result["transaction_evidence_ready"] is True
    assert result["participant_evidence_ready"] is False
    assert result["market_evidence_ready"] is False
