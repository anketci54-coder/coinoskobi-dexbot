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
                        "base_token_price_usd": "1.25",
                    }
                },
                {
                    "attributes": {
                        "address": "0xpool2",
                        "base_token_price_usd": "2.50",
                    }
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


def test_multi_pool_prices_reject_unbounded_list():
    pools = [f"0x{i}" for i in range(31)]

    try:
        GeckoScanner().pool_prices(pools)
    except ValueError:
        return

    raise AssertionError("unbounded pool list accepted")



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
        lambda seconds: sleeps.append(
            seconds
        ),
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
