from app.config.contracts import USDT, WBNB
from app.universe import scheduler
from app.universe.hot_path import BASE_TOKEN_SET, HotDeepPathRouter


def _row(token0, token1):
    return {
        "chain": "bsc",
        "dex": "pancakeswap_v2",
        "pool": "0xpool",
        "token0": token0,
        "token1": token1,
        "market_state": "HOT",
        "seismic_score": 10,
        "latest_price_usd": 1.0,
        "latest_liquidity_usd": 1000.0,
        "latest_volume_24h": 500.0,
        "latest_snapshot_source": "test",
    }


def test_scheduler_runtime_quote_contract_is_usdt_only():
    assert scheduler._OBSERVATION_QUOTE_TOKENS == (USDT.lower(),)


def test_hot_path_base_token_set_is_usdt_only():
    assert BASE_TOKEN_SET == frozenset({USDT.lower()})
    assert WBNB.lower() not in BASE_TOKEN_SET


def test_hot_path_accepts_token_usdt():
    candidate = HotDeepPathRouter._candidate(
        _row("0xtoken", USDT)
    )

    assert candidate is not None
    assert candidate["token"] == "0xtoken"
    assert candidate["quote_token"] == USDT.lower()


def test_hot_path_accepts_reversed_usdt_token():
    candidate = HotDeepPathRouter._candidate(
        _row(USDT, "0xtoken")
    )

    assert candidate is not None
    assert candidate["token"] == "0xtoken"
    assert candidate["quote_token"] == USDT.lower()


def test_hot_path_rejects_token_wbnb():
    assert (
        HotDeepPathRouter._candidate(
            _row("0xtoken", WBNB)
        )
        is None
    )
