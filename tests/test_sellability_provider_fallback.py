import requests

from app.risk import sellability as module


ADDRESS = (
    "0x1111111111111111111111111111111111111111"
)

PAIR = (
    "0x2222222222222222222222222222222222222222"
)


def _result(
    *,
    success=False,
    status=None,
    sellable=None,
):
    return {
        "success": success,
        "provider_success": success,
        "provider_status_code": status,
        "source": "sellability",
        "error": (
            None
            if success
            else str(status)
        ),
        "data": {
            "sellable": sellable,
            "honeypot": (
                False
                if sellable is True
                else (
                    True
                    if sellable is False
                    else None
                )
            ),
        },
    }


class FakeResponse:
    def __init__(
        self,
        status,
        sellable=None,
    ):
        self.status_code = status
        self._sellable = sellable

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                str(self.status_code),
                response=self,
            )

    def json(self):
        if self._sellable is True:
            return {
                "honeypotResult": {
                    "isHoneypot": False,
                },
                "simulationSuccess": True,
                "simulationResult": {},
            }

        if self._sellable is False:
            return {
                "honeypotResult": {
                    "isHoneypot": True,
                },
                "simulationSuccess": True,
                "simulationResult": {},
            }

        return {
            "honeypotResult": {},
            "simulationSuccess": False,
            "simulationResult": {},
        }


def _disable_cache(
    monkeypatch,
):
    cache = getattr(
        module,
        "_cache",
        None,
    )

    if cache is None:
        return

    if hasattr(
        cache,
        "get",
    ):
        monkeypatch.setattr(
            cache,
            "get",
            lambda *args, **kwargs: None,
        )

    if hasattr(
        cache,
        "set",
    ):
        monkeypatch.setattr(
            cache,
            "set",
            lambda *args, **kwargs: None,
        )


def _install_sequence(
    monkeypatch,
    sequence,
):
    calls = []

    helper = getattr(
        module,
        "_request_once",
        None,
    )

    if callable(helper):
        def fake_request_once(
            address,
            *,
            pair=None,
            simulate_liquidity=False,
        ):
            calls.append(
                (
                    bool(pair),
                    bool(simulate_liquidity),
                )
            )

            status, sellable = (
                sequence[
                    len(calls) - 1
                ]
            )

            return _result(
                success=(
                    status < 400
                ),
                status=status,
                sellable=sellable,
            )

        monkeypatch.setattr(
            module,
            "_request_once",
            fake_request_once,
        )

        return calls

    _disable_cache(
        monkeypatch
    )

    def fake_get(
        url,
        *,
        params=None,
        timeout=None,
        **kwargs,
    ):
        params = params or {}

        calls.append(
            (
                bool(
                    params.get("pair")
                ),
                str(
                    params.get(
                        "simulateLiquidity",
                        "",
                    )
                ).lower()
                == "true",
            )
        )

        status, sellable = (
            sequence[
                len(calls) - 1
            ]
        )

        return FakeResponse(
            status,
            sellable,
        )

    monkeypatch.setattr(
        module.requests,
        "get",
        fake_get,
    )

    return calls


def test_pair_404_retries_token_only(
    monkeypatch,
):
    calls = _install_sequence(
        monkeypatch,
        [
            (404, None),
            (200, True),
        ],
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert calls == [
        (True, False),
        (False, False),
    ]

    assert result["success"] is True
    assert result["data"]["sellable"] is True


def test_double_404_uses_simulated_liquidity(
    monkeypatch,
):
    calls = _install_sequence(
        monkeypatch,
        [
            (404, None),
            (404, None),
            (200, True),
        ],
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert calls == [
        (True, False),
        (False, False),
        (False, True),
    ]

    assert result["success"] is True
    assert result["data"]["sellable"] is True


def test_non_404_failure_stops_fallback(
    monkeypatch,
):
    calls = _install_sequence(
        monkeypatch,
        [
            (500, None),
        ],
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert calls == [
        (True, False),
    ]

    assert result["success"] is False
    assert result["data"]["sellable"] is None


def test_all_404_stays_unknown(
    monkeypatch,
):
    calls = _install_sequence(
        monkeypatch,
        [
            (404, None),
            (404, None),
            (404, None),
        ],
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert calls == [
        (True, False),
        (False, False),
        (False, True),
    ]

    assert result["success"] is False
    assert result["data"]["sellable"] is None


def test_explicit_unsellable_is_preserved(
    monkeypatch,
):
    calls = _install_sequence(
        monkeypatch,
        [
            (200, False),
        ],
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert calls == [
        (True, False),
    ]

    assert result["success"] is True
    assert result["data"]["sellable"] is False
    assert result["data"]["honeypot"] is True
