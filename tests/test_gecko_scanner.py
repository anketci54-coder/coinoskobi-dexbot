

def test_scanner_retries_429_then_succeeds(
    monkeypatch,
):
    import app.scanner.gecko_scanner as module

    calls = []
    sleeps = []

    class Response:
        def __init__(
            self,
            status_code,
        ):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(
                    f"http {self.status_code}"
                )

        def json(self):
            return {
                "data": [],
            }

    responses = iter([
        Response(429),
        Response(200),
    ])

    def fake_get(*args, **kwargs):
        calls.append(
            (args, kwargs)
        )

        return next(responses)

    monkeypatch.setattr(
        module.requests,
        "get",
        fake_get,
    )

    scanner = module.GeckoScanner()

    monkeypatch.setattr(
        scanner,
        "_wait_backoff",
        lambda value: (
            sleeps.append(value)
            or False
        ),
    )

    result = scanner.scan()

    assert result == []
    assert len(calls) == 2
    assert sleeps == [
        module.HTTP_429_BACKOFF_SECONDS
    ]


def test_scanner_rows_use_fetch_time_as_observation_time(
    monkeypatch,
):
    import app.scanner.gecko_scanner as module

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "data": [
                    {
                        "attributes": {
                            "address": "0xpool",
                            "base_token_price_usd": "1.25",
                        },
                        "relationships": {},
                    },
                ],
            }

    observed_at = 1_800_000_000.0
    monkeypatch.setattr(
        module.GeckoScanner,
        "_fetch",
        lambda self: Response(),
    )
    monkeypatch.setattr(
        module.time,
        "time",
        lambda: observed_at,
    )

    rows = module.GeckoScanner().scan()

    assert rows[0]["observed_at"] == observed_at


def test_scanner_429_retry_is_bounded_and_fails_closed(
    monkeypatch,
):
    import app.scanner.gecko_scanner as module

    calls = []
    sleeps = []

    class Response:
        status_code = 429

        def raise_for_status(self):
            raise RuntimeError(
                "http 429"
            )

    def fake_get(*args, **kwargs):
        calls.append(
            (args, kwargs)
        )

        return Response()

    monkeypatch.setattr(
        module.requests,
        "get",
        fake_get,
    )

    scanner = module.GeckoScanner()

    monkeypatch.setattr(
        scanner,
        "_wait_backoff",
        lambda value: (
            sleeps.append(value)
            or False
        ),
    )

    assert scanner.scan() == []

    assert len(calls) == (
        module.HTTP_429_MAX_RETRIES
        + 1
    )

    assert len(sleeps) == (
        module.HTTP_429_MAX_RETRIES
    )


def test_scanner_stop_interrupts_429_backoff(
    monkeypatch,
):
    import app.scanner.gecko_scanner as module

    calls = []
    scanner = module.GeckoScanner()

    class Response:
        status_code = 429

        def raise_for_status(self):
            raise RuntimeError(
                "http 429"
            )

    def fake_get(*args, **kwargs):
        calls.append(1)
        scanner.request_stop()
        return Response()

    monkeypatch.setattr(
        module.requests,
        "get",
        fake_get,
    )

    assert scanner.scan() == []
    assert len(calls) == 1
    assert scanner.is_stopping() is True
