import requests

import app.risk.sellability as module


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
        calls.append(
            (
                pair,
                simulate_liquidity,
            )
        )

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
        "_analyze_provider_once",
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

    assert (
        result["provider_success"]
        is True
    )

    assert (
        result["data"]["sellable"]
        is True
    )

    assert (
        result["data"][
            "provider_fallback_mode"
        ]
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
        calls.append(
            (
                pair,
                simulate_liquidity,
            )
        )

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
        "_analyze_provider_once",
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

    assert (
        result["provider_success"]
        is True
    )

    assert (
        result["data"][
            "provider_fallback_mode"
        ]
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
        calls.append(
            (
                pair,
                simulate_liquidity,
            )
        )

        return _result(
            status=500,
            error="500 server error",
        )

    monkeypatch.setattr(
        module,
        "_analyze_provider_once",
        fake,
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert calls == [
        (PAIR, False),
    ]

    assert (
        result["provider_success"]
        is False
    )

    assert (
        result["data"]["sellable"]
        is None
    )


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
        "_analyze_provider_once",
        fake,
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert (
        result["provider_success"]
        is False
    )

    assert (
        result["success"]
        is False
    )

    assert (
        result["data"]["sellable"]
        is None
    )

    assert (
        result["data"][
            "provider_fallback_mode"
        ]
        == "SIMULATE_LIQUIDITY"
    )


def test_explicit_honeypot_is_preserved(
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
        "_analyze_provider_once",
        fake,
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert (
        result["provider_success"]
        is True
    )

    assert (
        result["data"]["sellable"]
        is False
    )

    assert (
        result["data"]["honeypot"]
        is True
    )


def test_local_evidence_cannot_grant_provider_success(
    monkeypatch,
):
    class Cache:
        def get(
            self,
            *args,
            **kwargs,
        ):
            return None

        def set(
            self,
            *args,
            **kwargs,
        ):
            raise AssertionError(
                "provider failure must not be cached"
            )

    monkeypatch.setattr(
        module,
        "_cache",
        Cache(),
    )

    monkeypatch.setattr(
        module,
        "_local_evidence",
        lambda token, pair: {
            "completed": True,
            "lp_security": {},
            "exit_feasibility": {},
            "lp_error": None,
            "exit_error": None,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        },
    )

    class Response:
        status_code = 404

        def raise_for_status(
            self,
        ):
            exc = requests.HTTPError(
                "404 Client Error"
            )
            exc.response = self
            raise exc

        def json(
            self,
        ):
            return {}

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: Response(),
    )

    result = (
        module._analyze_provider_once(
            ADDRESS,
        )
    )

    assert (
        result["provider_success"]
        is False
    )

    assert (
        result["success"]
        is False
    )

    assert (
        result[
            "local_evidence_complete"
        ]
        is True
    )

    assert (
        result["data"][
            "local_evidence"
        ]["completed"]
        is True
    )


def test_provider_success_is_cacheable(
    monkeypatch,
):
    stored = []

    class Cache:
        def get(
            self,
            *args,
            **kwargs,
        ):
            return None

        def set(
            self,
            *args,
            **kwargs,
        ):
            stored.append(
                (
                    args,
                    kwargs,
                )
            )

    monkeypatch.setattr(
        module,
        "_cache",
        Cache(),
    )

    monkeypatch.setattr(
        module,
        "_local_evidence",
        lambda token, pair: {
            "completed": False,
            "lp_security": None,
            "exit_feasibility": None,
            "lp_error": None,
            "exit_error": None,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        },
    )

    class Response:
        status_code = 200

        def raise_for_status(
            self,
        ):
            return None

        def json(
            self,
        ):
            return {
                "simulationSuccess": True,
                "honeypotResult": {
                    "isHoneypot": False,
                },
                "simulationResult": {
                    "buyTax": 0,
                    "sellTax": 0,
                },
                "summary": {
                    "risk": "low",
                    "riskLevel": 1,
                },
            }

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: Response(),
    )

    result = (
        module._analyze_provider_once(
            ADDRESS,
        )
    )

    assert (
        result["provider_success"]
        is True
    )

    assert (
        result["success"]
        is True
    )

    assert (
        result["data"]["sellable"]
        is True
    )

    assert len(stored) == 1
