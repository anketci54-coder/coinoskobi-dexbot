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


def test_source_router_preserves_canonical_snapshot_market_fields():
    snapshot = {
        "schema_version": "GECKOTERMINAL_SNAPSHOT_V1",
        "chain": "bsc",
        "source": "geckoterminal",
        "dex": "pancakeswap_v2",
        "pool": "0xabcdef",
        "base_token": "0x123456",
        "quote_token": "0x999999",
        "price_usd": 0.001,
        "liquidity_usd": 35264.3232,
        "volume_h24_usd": 16192.275,
        "buys_h24": 45,
        "fdv_usd": 116845.6517,
        "observed_at": "2026-09-12T15:40:14+00:00",
    }

    result = normalize_source_rows(
        "geckoterminal",
        "bsc",
        [snapshot],
    )

    assert result["rejected"] == 0
    candidate = result["candidates"][0]

    assert candidate.source == "geckoterminal"
    assert candidate.liquidity == 35264.3232
    assert candidate.volume_24h == 16192.275
    assert candidate.buys_24h == 45
    assert candidate.fdv == 116845.6517
    assert candidate.price_usd == 0.001


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
