import app.risk.bytecode as risk_module
import pytest

from app.cache.analyzer_cache import AnalyzerCache


@pytest.fixture(autouse=True)
def isolated_risk_cache(tmp_path, monkeypatch):
    cache = AnalyzerCache(tmp_path / "risk-test-cache.db")

    monkeypatch.setattr(
        risk_module,
        "_cache",
        cache,
    )

    yield cache

    cache.close()




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


def test_risk_analyzer_uses_cache_without_rpc(monkeypatch):
    import json

    payload = {
        "success": True,
        "source": "risk",
        "data": {
            "code_size": 123,
            "owner": True,
            "transfer_owner": False,
            "renounce_owner": False,
            "pause": False,
            "unpause": False,
            "mint": False,
            "burn": False,
            "blacklist": False,
            "set_blacklist": False,
            "exclude_fee": False,
            "max_tx": False,
            "max_wallet": False,
        },
    }

    monkeypatch.setattr(
        risk_module._cache,
        "get",
        lambda *args, **kwargs: json.dumps(payload),
    )

    def fail_get_code(_):
        raise AssertionError("RPC should not be called")

    monkeypatch.setattr(
        risk_module.w3.eth,
        "get_code",
        fail_get_code,
    )

    result = risk_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result == payload


def test_risk_analyzer_writes_success_to_cache(monkeypatch):
    writes = []

    monkeypatch.setattr(
        risk_module._cache,
        "get",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        risk_module._cache,
        "set",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )

    class FakeCode:
        def hex(self):
            return "0x6001600055"

    monkeypatch.setattr(
        risk_module.w3.eth,
        "get_code",
        lambda _: FakeCode(),
    )

    result = risk_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is True
    assert len(writes) == 1


def test_risk_analyzer_does_not_cache_rpc_failure(monkeypatch):
    writes = []

    monkeypatch.setattr(
        risk_module._cache,
        "get",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        risk_module._cache,
        "set",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )

    def fail_get_code(_):
        raise RuntimeError("risk rpc failed")

    monkeypatch.setattr(
        risk_module.w3.eth,
        "get_code",
        fail_get_code,
    )

    result = risk_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is False
    assert writes == []
