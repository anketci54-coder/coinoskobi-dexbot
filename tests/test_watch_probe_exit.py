import app.learning.watch_probe_exit as module


def _reset_budget():
    module._BUDGET_WINDOW = None
    module._BUDGET_USED = 0


def test_verified_exit_requires_sellability_and_exact_quote(monkeypatch):
    _reset_budget()

    monkeypatch.setattr(
        module,
        "sellability_analyze",
        lambda token, pair=None: {
            "success": True,
            "data": {"sellable": True},
        },
    )
    monkeypatch.setattr(
        module,
        "_exact_router_exit_usdt",
        lambda token, pair, token_amount: 1.25,
    )

    result = module.probe_watch_exit(
        token="0xtoken",
        pool="0xpool",
        token_amount=10.0,
        now=60.0,
    )

    assert result["state"] == "VERIFIED"
    assert result["realizable_exit_usdt"] == 1.25
    assert result["quality"] == "SELLABILITY_PLUS_EXACT_ROUTE_QUOTE"
    assert result["execution_authority"] is False
    assert result["live_authority"] is False


def test_sellability_without_exact_quote_stays_limited(monkeypatch):
    _reset_budget()

    monkeypatch.setattr(
        module,
        "sellability_analyze",
        lambda token, pair=None: {
            "success": True,
            "data": {"sellable": True},
        },
    )
    monkeypatch.setattr(
        module,
        "_exact_router_exit_usdt",
        lambda token, pair, token_amount: None,
    )

    result = module.probe_watch_exit(
        token="0xtoken",
        pool="0xpool",
        token_amount=10.0,
        now=60.0,
    )

    assert result["state"] == "LIMITED"
    assert result["realizable_exit_usdt"] is None


def test_unverified_sellability_never_claims_realizable_exit(monkeypatch):
    _reset_budget()

    monkeypatch.setattr(
        module,
        "sellability_analyze",
        lambda token, pair=None: {
            "success": False,
            "data": {"sellable": None},
        },
    )

    result = module.probe_watch_exit(
        token="0xtoken",
        pool="0xpool",
        token_amount=10.0,
        now=60.0,
    )

    assert result["state"] == "UNVERIFIED"
    assert result["realizable_exit_usdt"] is None


def test_budget_caps_provider_attempts(monkeypatch):
    _reset_budget()
    calls = []

    def analyze(token, pair=None):
        calls.append((token, pair))
        return {
            "success": False,
            "data": {"sellable": None},
        }

    monkeypatch.setattr(
        module,
        "sellability_analyze",
        analyze,
    )

    results = [
        module.probe_watch_exit(
            token=f"0xtoken{i}",
            pool=f"0xpool{i}",
            token_amount=1.0,
            now=60.0,
        )
        for i in range(module.MAX_PROBES_PER_MINUTE + 2)
    ]

    assert len(calls) == module.MAX_PROBES_PER_MINUTE
    assert results[-1]["state"] == "DEFERRED"
    assert results[-1]["attempted"] is False
