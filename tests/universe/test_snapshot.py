import pytest

from app.universe.snapshot import (
    DEXSCREENER_MAX_BATCH,
    DexScreenerSnapshotClient,
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
        "baseToken": {"address": address(100)},
        "quoteToken": {"address": address(200)},
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
