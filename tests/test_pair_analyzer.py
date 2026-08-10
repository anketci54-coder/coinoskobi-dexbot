import app.analyzer.pair as pair_module
import pytest

from app.cache.analyzer_cache import AnalyzerCache


@pytest.fixture(autouse=True)
def isolated_pair_cache(tmp_path, monkeypatch):
    cache = AnalyzerCache(tmp_path / "pair-test-cache.db")

    monkeypatch.setattr(
        pair_module,
        "_cache",
        cache,
    )

    yield cache

    cache.close()




class FakeCall:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def call(self):
        if self.error:
            raise self.error
        return self.value


class FakeGetPair:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def __call__(self, *_):
        return FakeCall(self.value, self.error)


class FakeFunctions:
    def __init__(self, value=None, error=None):
        self.getPair = FakeGetPair(value, error)


class FakeFactory:
    def __init__(self, value=None, error=None):
        self.functions = FakeFunctions(value, error)


def test_pair_analyzer_returns_existing_pair(monkeypatch):
    pair_address = "0x0000000000000000000000000000000000000002"

    monkeypatch.setattr(
        pair_module,
        "factory",
        FakeFactory(value=pair_address),
    )

    result = pair_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is True
    assert result["data"]["exists"] is True
    assert result["data"]["pair"] == pair_address
    assert result["data"]["quote_ok"] is True


def test_pair_analyzer_returns_missing_pair(monkeypatch):
    monkeypatch.setattr(
        pair_module,
        "factory",
        FakeFactory(value=pair_module.ZERO),
    )

    result = pair_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is True
    assert result["data"]["exists"] is False
    assert result["data"]["pair"] is None
    assert result["data"]["quote_ok"] is False


def test_pair_analyzer_returns_unknown_on_rpc_failure(monkeypatch):
    monkeypatch.setattr(
        pair_module,
        "factory",
        FakeFactory(error=RuntimeError("rpc unavailable")),
    )

    result = pair_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is False
    assert result["data"] == {}
    assert "rpc unavailable" in result["error"]


def test_pair_analyzer_uses_cache_without_rpc(monkeypatch):
    import json

    payload = {
        "success": True,
        "source": "pair",
        "data": {
            "exists": True,
            "pair": "0x0000000000000000000000000000000000000002",
            "quote_ok": True,
        },
    }

    monkeypatch.setattr(
        pair_module._cache,
        "get",
        lambda *args, **kwargs: json.dumps(payload),
    )

    class FailFunctions:
        def getPair(self, *_):
            raise AssertionError("RPC should not be called")

    class FailFactory:
        functions = FailFunctions()

    monkeypatch.setattr(
        pair_module,
        "factory",
        FailFactory(),
    )

    result = pair_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result == payload


def test_pair_analyzer_writes_success_to_cache(monkeypatch):
    writes = []

    monkeypatch.setattr(
        pair_module._cache,
        "get",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        pair_module._cache,
        "set",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )

    class FakeCall:
        def call(self):
            return "0x0000000000000000000000000000000000000002"

    class FakeFunctions:
        def getPair(self, *_):
            return FakeCall()

    class FakeFactory:
        functions = FakeFunctions()

    monkeypatch.setattr(
        pair_module,
        "factory",
        FakeFactory(),
    )

    result = pair_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is True
    assert result["data"]["exists"] is True
    assert len(writes) == 1


def test_pair_analyzer_does_not_cache_rpc_failure(monkeypatch):
    writes = []

    monkeypatch.setattr(
        pair_module._cache,
        "get",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        pair_module._cache,
        "set",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )

    class FailCall:
        def call(self):
            raise RuntimeError("pair rpc failed")

    class FailFunctions:
        def getPair(self, *_):
            return FailCall()

    class FailFactory:
        functions = FailFunctions()

    monkeypatch.setattr(
        pair_module,
        "factory",
        FailFactory(),
    )

    result = pair_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is False
    assert writes == []
