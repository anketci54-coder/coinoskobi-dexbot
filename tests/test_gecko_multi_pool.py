from app.scanner.gecko_scanner import GeckoScanner


class Response:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "data": [
                {
                    "attributes": {
                        "address": "0xpool1",
                        "name": "TOKEN1 / WBNB",
                        "base_token_price_usd": "1.25",
                        "fdv_usd": "1250000",
                        "market_cap_usd": "1000000",
                        "reserve_in_usd": "250000",
                        "volume_usd": {
                            "h24": "750000",
                        },
                        "transactions": {
                            "h24": {
                                "buys": 321,
                            },
                        },
                        "pool_created_at": (
                            "2026-08-25T00:00:00Z"
                        ),
                    },
                    "relationships": {
                        "base_token": {
                            "data": {
                                "id": "bsc_0xtoken1",
                            },
                        },
                        "quote_token": {
                            "data": {
                                "id": "bsc_0xquote1",
                            },
                        },
                        "dex": {
                            "data": {
                                "id": "pancakeswap_v2",
                            },
                        },
                    },
                },
                {
                    "attributes": {
                        "address": "0xpool2",
                        "name": "TOKEN2 / WBNB",
                        "base_token_price_usd": "2.50",
                        "fdv_usd": "2500000",
                        "market_cap_usd": "2000000",
                        "reserve_in_usd": "500000",
                        "volume_usd": {
                            "h24": "900000",
                        },
                        "transactions": {
                            "h24": {
                                "buys": 654,
                            },
                        },
                        "pool_created_at": (
                            "2026-08-24T00:00:00Z"
                        ),
                    },
                    "relationships": {
                        "base_token": {
                            "data": {
                                "id": "bsc_0xtoken2",
                            },
                        },
                        "quote_token": {
                            "data": {
                                "id": "bsc_0xquote2",
                            },
                        },
                        "dex": {
                            "data": {
                                "id": "pancakeswap_v2",
                            },
                        },
                    },
                },
            ]
        }


def test_multi_pool_prices_use_one_request(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(
        "app.scanner.gecko_scanner.requests.get",
        get,
    )
    monkeypatch.setattr(
        (
            "app.scanner.gecko_scanner."
            "persist_registered_followup_snapshots"
        ),
        lambda rows: None,
    )

    prices = GeckoScanner().pool_prices([
        "0xpool1",
        "0xpool2",
        "0xpool1",
    ])

    assert prices == {
        "0xpool1": 1.25,
        "0xpool2": 2.50,
    }
    assert len(calls) == 1


def test_multi_pool_snapshot_contains_fresh_market_facts(
    monkeypatch,
):
    calls = []
    persisted = []

    def get(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(
        "app.scanner.gecko_scanner.requests.get",
        get,
    )
    monkeypatch.setattr(
        (
            "app.scanner.gecko_scanner."
            "persist_registered_followup_snapshots"
        ),
        lambda rows: persisted.extend(rows),
    )

    rows = GeckoScanner().pool_snapshots([
        "0xpool1",
        "0xpool2",
    ])

    assert len(calls) == 1
    assert len(rows) == 2

    first = rows[0]
    assert first["pool"] == "0xpool1"
    assert first["base_token"] == "bsc_0xtoken1"
    assert first["quote_token"] == "bsc_0xquote1"
    assert first["dex"] == "pancakeswap_v2"
    assert first["price_usd"] == 1.25
    assert first["liquidity"] == 250000.0
    assert first["volume_24h"] == 750000.0
    assert first["buys_24h"] == 321
    assert first["fdv"] == 1250000.0
    assert first["market_cap"] == 1000000.0
    assert persisted == rows


def test_multi_pool_prices_reject_unbounded_list():
    pools = [f"0x{i}" for i in range(31)]

    try:
        GeckoScanner().pool_prices(pools)
    except ValueError:
        return

    raise AssertionError(
        "unbounded pool list accepted"
    )


def test_multi_pool_prices_back_off_and_retry_429(
    monkeypatch,
):
    calls = []
    sleeps = []

    class RateLimitedResponse:
        status_code = 429

        def raise_for_status(self):
            raise RuntimeError(
                "rate limited"
            )

    responses = [
        RateLimitedResponse(),
        Response(),
    ]

    def get(url, **kwargs):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(
        "app.scanner.gecko_scanner.requests.get",
        get,
    )
    monkeypatch.setattr(
        "app.scanner.gecko_scanner.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    monkeypatch.setattr(
        (
            "app.scanner.gecko_scanner."
            "persist_registered_followup_snapshots"
        ),
        lambda rows: None,
    )

    prices = GeckoScanner().pool_prices([
        "0xpool1",
        "0xpool2",
    ])

    assert prices == {
        "0xpool1": 1.25,
        "0xpool2": 2.50,
    }
    assert len(calls) == 2
    assert sleeps == [2]
