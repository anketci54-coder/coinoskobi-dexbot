import pytest

from app.universe.snapshot import (
    DEXSCREENER_MAX_BATCH,
    DexScreenerSnapshotClient,
    GECKOTERMINAL_SOURCE,
    GeckoTerminalSnapshotClient,
    ProviderStickySnapshotClient,
    SNAPSHOT_SOURCE,
)


def address(value):
    return "0x" + f"{value:040x}"


class Response:
    def __init__(self, payload):
        self.payload = payload
        self.raised = False

    def raise_for_status(self):
        self.raised = True

    def json(self):
        return self.payload


class Session:
    def __init__(self, payload):
        self.response = Response(payload)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def pair(pool, **overrides):
    row = {
        "chainId": "bsc",
        "dexId": "pancakeswap",
        "pairAddress": pool,
        "baseToken": {
            "address": address(100),
            "symbol": "ALPHA",
            "name": "Alpha Token",
        },
        "quoteToken": {
            "address": address(200),
            "symbol": "WBNB",
            "name": "Wrapped BNB",
        },
        "priceUsd": "1.25",
        "liquidity": {"usd": 5000},
        "fdv": 9000,
        "marketCap": 8000,
        "pairCreatedAt": 1700000000000,
        "txns": {"m5": {"buys": 3, "sells": 2},
                 "h1": {"buys": 9, "sells": 4}},
        "volume": {"m5": 100, "h1": 500},
        "priceChange": {"m5": 0.5, "h1": 3.0},
    }
    row.update(overrides)
    return row


def gecko_pair(pool, **overrides):
    row = {
        "attributes": {
            "address": pool,
            "name": "ALPHA / WBNB",
            "base_token_price_usd": "1.20",
            "reserve_in_usd": "4990",
            "fdv_usd": "8900",
            "market_cap_usd": "7900",
            "pool_created_at": "2026-08-25T00:00:00Z",
            "transactions": {
                "m5": {"buys": 4, "sells": 1},
                "h1": {"buys": 8, "sells": 3},
                "h6": {"buys": 20, "sells": 10},
                "h24": {"buys": 40, "sells": 20},
            },
            "volume_usd": {
                "m5": "101", "h1": "501", "h6": "900", "h24": "1400",
            },
            "price_change_percentage": {
                "m5": "0.4", "h1": "2.8", "h6": "5.0", "h24": "8.0",
            },
        },
        "relationships": {
            "base_token": {"data": {"id": "bsc_" + address(100)}},
            "quote_token": {"data": {"id": "bsc_" + address(200)}},
            "dex": {"data": {"id": "pancakeswap_v2"}},
        },
    }
    row.update(overrides)
    return row


def test_fetch_is_one_bounded_exact_pool_request_and_normalizes_facts():
    first, second = address(1), address(2)
    session = Session({"pairs": [pair(first), pair(second)]})
    client = DexScreenerSnapshotClient(
        session=session,
        now_func=lambda: "2026-08-25T15:00:00+00:00",
    )
    rows = client.fetch([
        {"pool": first.upper(), "dex": "pancakeswap_v2"},
        {"pool": second, "dex": "pancakeswap_v3"},
    ])

    assert len(session.calls) == 1
    assert session.calls[0][0].endswith(f"/{first},{second}")
    assert session.calls[0][1]["timeout"] == 10.0
    assert session.response.raised is True
    assert [row["dex"] for row in rows] == [
        "pancakeswap_v2", "pancakeswap_v3"
    ]
    assert rows[0]["txns_m5"] == 5
    assert rows[0]["volume_m5_usd"] == 100.0
    assert rows[0]["change_h1"] == 3.0
    assert rows[0]["observed_at"] == "2026-08-25T15:00:00+00:00"
    assert rows[0]["base_symbol"] == "ALPHA"
    assert rows[0]["quote_symbol"] == "WBNB"
    assert rows[0]["base_name"] == "Alpha Token"
    assert rows[0]["quote_name"] == "Wrapped BNB"
    assert rows[0]["display_name"] == "ALPHA / WBNB"


def test_batch_limit_is_strict_and_makes_no_provider_call():
    session = Session({"pairs": []})
    client = DexScreenerSnapshotClient(session=session)
    pools = [
        {"pool": address(value), "dex": "pancakeswap_v2"}
        for value in range(1, DEXSCREENER_MAX_BATCH + 2)
    ]
    with pytest.raises(ValueError, match="exceeds 30"):
        client.fetch(pools)
    assert session.calls == []


def test_empty_batch_makes_no_provider_call():
    session = Session({"pairs": []})
    assert DexScreenerSnapshotClient(session=session).fetch([]) == []
    assert session.calls == []


def test_only_requested_bsc_pancake_pairs_are_returned():
    wanted = address(1)
    session = Session({"pairs": [
        pair(wanted),
        pair(address(2)),
        pair(wanted, chainId="ethereum"),
        pair(wanted, dexId="uniswap"),
    ]})
    rows = DexScreenerSnapshotClient(session=session).fetch([
        {"pool": wanted, "dex": "pancakeswap_v2"}
    ])
    assert len(rows) == 1
    assert rows[0]["pool"] == wanted


def test_duplicate_identity_collapses_but_conflicting_dex_fails_closed():
    pool = address(1)
    session = Session({"pairs": [pair(pool)]})
    client = DexScreenerSnapshotClient(session=session)
    assert len(client.fetch([
        {"pool": pool, "dex": "pancakeswap_v2"},
        {"pool": pool, "dex": "pancakeswap_v2"},
    ])) == 1
    with pytest.raises(ValueError, match="conflicting"):
        client.fetch([
            {"pool": pool, "dex": "pancakeswap_v2"},
            {"pool": pool, "dex": "pancakeswap_v3"},
        ])


def test_malformed_payload_fails_closed():
    client = DexScreenerSnapshotClient(
        session=Session({"pairs": {"unexpected": True}})
    )
    with pytest.raises(ValueError, match="invalid DexScreener"):
        client.fetch([{"pool": address(1), "dex": "pancakeswap_v2"}])


def test_gecko_exact_pool_normalizes_same_universe_metric_contract():
    pool = address(1)
    session = Session({"data": [gecko_pair(pool)]})
    client = GeckoTerminalSnapshotClient(
        session=session,
        now_func=lambda: "2026-08-28T15:00:00+00:00",
    )

    rows = client.fetch([{"pool": pool, "dex": "pancakeswap_v2"}])

    assert len(session.calls) == 1
    assert session.calls[0][0].endswith("/" + pool)
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == GECKOTERMINAL_SOURCE
    assert row["pool"] == pool
    assert row["dex"] == "pancakeswap_v2"
    assert row["base_token"] == address(100)
    assert row["quote_token"] == address(200)
    assert row["display_name"] == "ALPHA / WBNB"
    assert row["price_usd"] == 1.2
    assert row["liquidity_usd"] == 4990.0
    assert row["txns_m5"] == 5
    assert row["volume_m5_usd"] == 101.0
    assert row["change_m5"] == 0.4
    assert row["observed_at"] == "2026-08-28T15:00:00+00:00"
    assert row["pair_created_at_ms"] is not None


def test_gecko_rejects_non_pancake_response_without_inventing_snapshot():
    pool = address(1)
    raw = gecko_pair(pool)
    raw["relationships"]["dex"]["data"]["id"] = "uniswap_v3"
    client = GeckoTerminalSnapshotClient(session=Session({"data": [raw]}))
    assert client.fetch([{"pool": pool, "dex": "pancakeswap_v2"}]) == []


class Provider:
    def __init__(self, source, returned):
        self.source = source
        self.returned = set(returned)
        self.calls = []

    def fetch(self, pools):
        rows = [dict(row) for row in pools]
        self.calls.append(rows)
        return [
            {
                "chain": "bsc",
                "dex": row["dex"],
                "pool": row["pool"],
                "source": self.source,
                "observed_at": "2026-08-28T15:00:00+00:00",
            }
            for row in rows
            if row["pool"] in self.returned
        ]


def test_unbound_pool_uses_gecko_only_after_dexscreener_omission():
    first, second = address(1), address(2)
    primary = Provider(SNAPSHOT_SOURCE, {first})
    fallback = Provider(GECKOTERMINAL_SOURCE, {second})
    client = ProviderStickySnapshotClient(primary=primary, fallback=fallback)

    rows = client.fetch([
        {"pool": first, "dex": "pancakeswap_v2"},
        {"pool": second, "dex": "pancakeswap_v2"},
    ])

    assert [row["pool"] for row in primary.calls[0]] == [first, second]
    assert [row["pool"] for row in fallback.calls[0]] == [second]
    assert [(row["pool"], row["source"]) for row in rows] == [
        (first, SNAPSHOT_SOURCE),
        (second, GECKOTERMINAL_SOURCE),
    ]


def test_sticky_source_never_switches_provider_on_temporary_miss():
    dex_sticky, gecko_sticky, unbound = address(1), address(2), address(3)
    primary = Provider(SNAPSHOT_SOURCE, {unbound})
    fallback = Provider(GECKOTERMINAL_SOURCE, {gecko_sticky, dex_sticky})
    client = ProviderStickySnapshotClient(primary=primary, fallback=fallback)

    rows = client.fetch([
        {"pool": dex_sticky, "dex": "pancakeswap_v2",
         "latest_snapshot_source": SNAPSHOT_SOURCE},
        {"pool": gecko_sticky, "dex": "pancakeswap_v2",
         "latest_snapshot_source": GECKOTERMINAL_SOURCE},
        {"pool": unbound, "dex": "pancakeswap_v2"},
    ])

    assert [row["pool"] for row in primary.calls[0]] == [dex_sticky, unbound]
    assert [row["pool"] for row in fallback.calls[0]] == [gecko_sticky]
    assert [(row["pool"], row["source"]) for row in rows] == [
        (gecko_sticky, GECKOTERMINAL_SOURCE),
        (unbound, SNAPSHOT_SOURCE),
    ]
    assert dex_sticky not in {row["pool"] for row in rows}


def test_unknown_sticky_source_fails_closed_before_provider_calls():
    primary = Provider(SNAPSHOT_SOURCE, set())
    fallback = Provider(GECKOTERMINAL_SOURCE, set())
    client = ProviderStickySnapshotClient(primary=primary, fallback=fallback)

    with pytest.raises(ValueError, match="unsupported sticky"):
        client.fetch([{
            "pool": address(1),
            "dex": "pancakeswap_v2",
            "latest_snapshot_source": "other-provider",
        }])

    assert primary.calls == []
    assert fallback.calls == []
