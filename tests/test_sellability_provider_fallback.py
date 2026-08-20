from app.risk import sellability as module


ADDRESS = "0x1111111111111111111111111111111111111111"
PAIR = "0x2222222222222222222222222222222222222222"


def _result(
    *,
    success=False,
    status=None,
    error=None,
    sellable=None,
):
    return {
        "success": success,
        "provider_success": success,
        "provider_status_code": status,
        "source": "sellability",
        "error": error,
        "data": {
            "sellable": sellable,
            "honeypot": (
                False
                if sellable is True
                else None
            ),
        },
    }


def test_pair_404_retries_token_only(
    monkeypatch,
):
    calls = []

    def fake(
        address,
        *,
        pair=None,
        simulate_liquidity=False,
    ):
        calls.append((pair, simulate_liquidity))

        if pair:
            return _result(
                status=404,
                error="404",
            )

        return _result(
            success=True,
            status=200,
            sellable=True,
        )

    monkeypatch.setattr(
        module,
        "_request_once",
        fake,
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert calls == [
        (PAIR, False),
        (None, False),
    ]
    assert result["success"] is True
    assert result["data"]["sellable"] is True
    assert (
        result["data"]["provider_fallback_mode"]
        == "TOKEN_ONLY"
    )


def test_double_404_uses_simulate_liquidity(
    monkeypatch,
):
    calls = []

    def fake(
        address,
        *,
        pair=None,
        simulate_liquidity=False,
    ):
        calls.append((pair, simulate_liquidity))

        if simulate_liquidity:
            return _result(
                success=True,
                status=200,
                sellable=True,
            )

        return _result(
            status=404,
            error="404",
        )

    monkeypatch.setattr(
        module,
        "_request_once",
        fake,
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert calls == [
        (PAIR, False),
        (None, False),
        (None, True),
    ]
    assert result["success"] is True
    assert (
        result["data"]["provider_fallback_mode"]
        == "SIMULATE_LIQUIDITY"
    )


def test_non_404_failure_is_not_retried(
    monkeypatch,
):
    calls = []

    def fake(
        address,
        *,
        pair=None,
        simulate_liquidity=False,
    ):
        calls.append((pair, simulate_liquidity))
        return _result(
            status=500,
            error="500 server error",
        )

    monkeypatch.setattr(
        module,
        "_request_once",
        fake,
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert calls == [(PAIR, False)]
    assert result["success"] is False
    assert result["data"]["sellable"] is None


def test_all_404_remains_unknown(
    monkeypatch,
):
    def fake(
        address,
        *,
        pair=None,
        simulate_liquidity=False,
    ):
        return _result(
            status=404,
            error="404",
        )

    monkeypatch.setattr(
        module,
        "_request_once",
        fake,
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert result["success"] is False
    assert result["provider_success"] is False
    assert result["data"]["sellable"] is None
    assert (
        result["data"]["provider_fallback_mode"]
        == "SIMULATE_LIQUIDITY"
    )


def test_explicit_unsellable_result_is_preserved(
    monkeypatch,
):
    def fake(
        address,
        *,
        pair=None,
        simulate_liquidity=False,
    ):
        return {
            "success": True,
            "provider_success": True,
            "provider_status_code": 200,
            "source": "sellability",
            "error": None,
            "data": {
                "sellable": False,
                "honeypot": True,
            },
        }

    monkeypatch.setattr(
        module,
        "_request_once",
        fake,
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert result["success"] is True
    assert result["data"]["sellable"] is False
    assert result["data"]["honeypot"] is True
