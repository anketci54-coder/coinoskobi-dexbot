import pytest

from app.scanner.adapters.registry import (
    get_adapter,
    normalize,
)


def row():
    return {
        "pool": "0xABCDEF",
        "base_token": "bsc_0x123456",
        "quote_token": "bsc_0x999999",
        "dex": "pancakeswap_v2",
        "liquidity": 12000,
        "volume_24h": 8000,
        "buys_24h": 42,
        "fdv": 100000,
        "price_usd": 0.001,
        "created_at": None,
    }


def test_gecko_bsc_adapter_exists():
    adapter = get_adapter(
        "gecko_bsc"
    )

    assert callable(adapter)


def test_adapter_produces_common_candidate():
    candidate = normalize(
        "gecko_bsc",
        row(),
    )

    assert candidate.chain == "bsc"
    assert candidate.chain_id == 56
    assert candidate.token == "0x123456"

    assert candidate.token_identity_key == (
        "bsc:0x123456"
    )


def test_unknown_adapter_fails():
    with pytest.raises(KeyError):
        get_adapter("missing")
