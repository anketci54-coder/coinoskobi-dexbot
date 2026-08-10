import pytest

from app.scanner.adapters.source_router import (
    normalize_source_rows,
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


def test_source_router_uses_source_network_binding():
    result = normalize_source_rows(
        "geckoterminal",
        "bsc",
        [row()],
    )

    assert result["source"] == "geckoterminal"
    assert result["network"] == "bsc"
    assert result["chain_id"] == 56
    assert result["adapter"] == "gecko_bsc"
    assert result["rejected"] == 0

    candidate = result["candidates"][0]

    assert candidate.chain == "bsc"
    assert candidate.token == "0x123456"
    assert candidate.token_identity_key == (
        "bsc:0x123456"
    )


def test_source_router_isolates_bad_row():
    bad = row()
    bad["pool"] = None

    result = normalize_source_rows(
        "geckoterminal",
        "bsc",
        [
            row(),
            bad,
        ],
    )

    assert len(result["candidates"]) == 1
    assert result["rejected"] == 1


def test_disabled_network_is_rejected():
    with pytest.raises(RuntimeError):
        normalize_source_rows(
            "geckoterminal",
            "base",
            [row()],
        )


def test_unknown_source_fails():
    with pytest.raises(KeyError):
        normalize_source_rows(
            "missing-source",
            "bsc",
            [row()],
        )
