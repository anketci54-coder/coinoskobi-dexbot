from datetime import datetime, timedelta, timezone

from app.filter.ingress_gate import (
    IngressGate,
    LANE_ACTIVE,
    LANE_DEFER,
    LANE_DROP,
)


def iso(delta):
    return (
        datetime.now(timezone.utc)
        + delta
    ).isoformat()


def good_row(**changes):
    row = {
        "pool": "pool-1",
        "token": "bsc_0x0000000000000000000000000000000000000001",
        "name": "Example",
        "dex": "pancakeswap_v2",
        "liquidity": 10_000,
        "volume_24h": 5_000,
        "buys_24h": 20,
        "fdv": 100_000,
        "price_usd": 0.001,
        "created_at": iso(
            timedelta(hours=-1)
        ),
        "updated_at": iso(
            timedelta(seconds=-10)
        ),
    }

    row.update(changes)

    return row


def test_valid_candidate_is_active():
    result = IngressGate().classify(
        good_row()
    )

    assert result["lane"] == LANE_ACTIVE


def test_low_liquidity_candidate_is_deferred():
    result = IngressGate().classify(
        good_row(liquidity=100)
    )

    assert result["lane"] == LANE_DEFER
    assert "LOW_LIQUIDITY" in result["reason"]


def test_low_volume_candidate_is_deferred():
    result = IngressGate().classify(
        good_row(volume_24h=10)
    )

    assert result["lane"] == LANE_DEFER
    assert "LOW_VOLUME" in result["reason"]


def test_unsupported_dex_is_dropped():
    result = IngressGate().classify(
        good_row(dex="unknown_dex")
    )

    assert result["lane"] == LANE_DROP
    assert result["reason"] == "UNSUPPORTED_DEX"


def test_missing_token_is_dropped():
    result = IngressGate().classify(
        good_row(token=None)
    )

    assert result["lane"] == LANE_DROP
    assert result["reason"] == "MISSING_TOKEN"


def test_invalid_market_data_is_dropped():
    result = IngressGate().classify(
        good_row(liquidity="bad")
    )

    assert result["lane"] == LANE_DROP
    assert result["reason"] == "INVALID_MARKET_DATA"


def test_stale_cache_is_dropped():
    result = IngressGate().classify(
        good_row(
            updated_at=iso(
                timedelta(hours=-1)
            )
        )
    )

    assert result["lane"] == LANE_DROP
    assert result["reason"] == "STALE_CACHE"


def test_batch_classification_counts_lanes():
    rows = [
        good_row(pool="active"),
        good_row(
            pool="defer",
            liquidity=100,
        ),
        good_row(
            pool="drop",
            token=None,
        ),
    ]

    result = IngressGate().classify_many(
        rows
    )

    assert result["stats"]["input"] == 3
    assert result["stats"]["active"] == 1
    assert result["stats"]["deferred"] == 1
    assert result["stats"]["dropped"] == 1


def test_ingress_accepts_common_candidate_observed_at():
    from datetime import datetime, timezone

    row = {
        "chain": "bsc",
        "chain_id": 56,
        "pool": "0xpool",
        "token": "0xtoken",
        "quote_token": "0xquote",
        "source": "geckoterminal",
        "dex": "pancakeswap_v2",
        "liquidity": 20_000,
        "volume_24h": 5_000,
        "buys_24h": 20,
        "fdv": 100_000,
        "price_usd": 0.001,
        "created_at": None,
        "observed_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    result = IngressGate().classify(row)

    assert result["lane"] == "ACTIVE"
