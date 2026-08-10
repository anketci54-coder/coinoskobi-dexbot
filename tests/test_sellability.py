import app.risk.sellability as module


TOKEN = (
    "0x000000000000000000000000"
    "0000000000000001"
)


class FakeResponse:
    def __init__(
        self,
        payload,
        status_code=200,
    ):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(
                f"http {self.status_code}"
            )

    def json(self):
        return self.payload


def disable_cache(
    monkeypatch,
):
    monkeypatch.setattr(
        module._cache,
        "get",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        module._cache,
        "set",
        lambda *args, **kwargs: None,
    )


def test_confirmed_honeypot_is_unsellable(
    monkeypatch,
):
    disable_cache(monkeypatch)

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: (
            FakeResponse({
                "simulationSuccess": False,
                "honeypotResult": {
                    "isHoneypot": True,
                    "honeypotReason": (
                        "TRANSFER_FROM_FAILED"
                    ),
                },
                "summary": {
                    "risk": "honeypot",
                    "riskLevel": 100,
                },
            })
        ),
    )

    result = module.analyze(
        TOKEN
    )

    assert result["success"] is True

    data = result["data"]

    assert data["honeypot"] is True
    assert data["sellable"] is False

    assert (
        data["honeypot_reason"]
        == "TRANSFER_FROM_FAILED"
    )


def test_successful_non_honeypot_is_sellable(
    monkeypatch,
):
    disable_cache(monkeypatch)

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: (
            FakeResponse({
                "simulationSuccess": True,
                "honeypotResult": {
                    "isHoneypot": False,
                },
                "simulationResult": {
                    "buyTax": 2,
                    "sellTax": 4,
                    "transferTax": 0,
                    "buyGas": "150000",
                    "sellGas": "175000",
                },
                "summary": {
                    "risk": "low",
                    "riskLevel": 10,
                },
            })
        ),
    )

    result = module.analyze(
        TOKEN
    )

    assert result["success"] is True

    data = result["data"]

    assert data["honeypot"] is False
    assert data["sellable"] is True

    assert data["buy_tax"] == 2
    assert data["sell_tax"] == 4
    assert data["buy_gas"] == "150000"
    assert data["sell_gas"] == "175000"


def test_failed_simulation_stays_unknown(
    monkeypatch,
):
    disable_cache(monkeypatch)

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: (
            FakeResponse({
                "simulationSuccess": False,
                "simulationError": (
                    "simulation unavailable"
                ),
                "summary": {
                    "risk": "unknown",
                },
            })
        ),
    )

    result = module.analyze(
        TOKEN
    )

    assert result["success"] is True

    data = result["data"]

    assert data["honeypot"] is None
    assert data["sellable"] is None


def test_provider_failure_is_unknown_not_block(
    monkeypatch,
):
    disable_cache(monkeypatch)

    def fail(*args, **kwargs):
        raise TimeoutError(
            "provider timeout"
        )

    monkeypatch.setattr(
        module.requests,
        "get",
        fail,
    )

    result = module.analyze(
        TOKEN
    )

    assert result["success"] is False
    assert (
        result["data"]["honeypot"]
        is None
    )
    assert (
        result["data"]["sellable"]
        is None
    )


def test_result_is_cached(
    monkeypatch,
):
    stored = {}

    monkeypatch.setattr(
        module._cache,
        "get",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        module._cache,
        "set",
        lambda namespace, key, payload: (
            stored.update({
                "namespace": namespace,
                "key": key,
                "payload": payload,
            })
        ),
    )

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: (
            FakeResponse({
                "simulationSuccess": True,
                "honeypotResult": {
                    "isHoneypot": False,
                },
                "simulationResult": {},
                "summary": {
                    "risk": "low",
                    "riskLevel": 1,
                },
            })
        ),
    )

    result = module.analyze(
        TOKEN
    )

    assert result["success"] is True
    assert (
        stored["namespace"]
        == "sellability"
    )
    assert stored["key"].startswith(
        "bsc:"
    )
