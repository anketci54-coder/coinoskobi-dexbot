

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

    monkeypatch.setattr(
        module.time,
        "sleep",
        lambda value: sleeps.append(
            value
        ),
    )

    result = module.GeckoScanner().scan()

    assert result == []
    assert len(calls) == 2
    assert sleeps == [
        module.HTTP_429_BACKOFF_SECONDS
    ]


def test_scanner_429_retry_is_bounded(
    monkeypatch,
):
    import pytest
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

    monkeypatch.setattr(
        module.time,
        "sleep",
        lambda value: sleeps.append(
            value
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="429",
    ):
        module.GeckoScanner().scan()

    assert len(calls) == (
        module.HTTP_429_MAX_RETRIES
        + 1
    )

    assert len(sleeps) == (
        module.HTTP_429_MAX_RETRIES
    )
