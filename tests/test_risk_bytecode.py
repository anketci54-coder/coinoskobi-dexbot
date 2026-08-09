import app.risk.bytecode as risk_module


class FakeCode:
    def __init__(self, value):
        self.value = value

    def hex(self):
        return self.value


def test_risk_analyzer_reads_bytecode_flags(monkeypatch):
    code = (
        "00"
        + risk_module.SIGNATURES["owner"]
        + risk_module.SIGNATURES["mint"]
        + risk_module.SIGNATURES["blacklist"]
        + "00"
    )

    monkeypatch.setattr(
        risk_module.w3.eth,
        "get_code",
        lambda _: FakeCode(code),
    )

    result = risk_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    data = result["data"]

    assert result["success"] is True
    assert data["owner"] is True
    assert data["mint"] is True
    assert data["blacklist"] is True
    assert data["pause"] is False


def test_risk_analyzer_returns_unknown_on_rpc_failure(monkeypatch):
    def fail_get_code(_):
        raise RuntimeError("rpc unavailable")

    monkeypatch.setattr(
        risk_module.w3.eth,
        "get_code",
        fail_get_code,
    )

    result = risk_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is False
    assert result["data"] == {}
    assert "rpc unavailable" in result["error"]


def test_pipeline_strategy_does_not_treat_failed_risk_as_safe(monkeypatch):
    from app.strategy.engine import StrategyEngine

    def fail_get_code(_):
        raise RuntimeError("rpc unavailable")

    monkeypatch.setattr(
        risk_module.w3.eth,
        "get_code",
        fail_get_code,
    )

    risk_result = risk_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    strategy = StrategyEngine().evaluate(
        token={},
        pair={"exists": False, "quote_ok": False},
        risk=risk_result["data"],
    )["data"]

    assert risk_result["success"] is False
    assert strategy["score"] == 0
    assert strategy["decision"] == "REJECT"
