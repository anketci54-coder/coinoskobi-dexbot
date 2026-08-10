import app.analyzer.token as token_module
import pytest

from app.cache.analyzer_cache import AnalyzerCache


@pytest.fixture(autouse=True)
def isolated_token_cache(tmp_path, monkeypatch):
    cache = AnalyzerCache(tmp_path / "token-test-cache.db")

    monkeypatch.setattr(
        token_module,
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


class FakeFunction:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def __call__(self):
        return FakeCall(self.value, self.error)


class FakeFunctions:
    def __init__(
        self,
        name="Example Token",
        symbol="EXT",
        decimals=18,
        total_supply=1_000_000 * 10**18,
    ):
        self.name = FakeFunction(name)
        self.symbol = FakeFunction(symbol)
        self.decimals = FakeFunction(decimals)
        self.totalSupply = FakeFunction(total_supply)


class FakeContract:
    def __init__(self, functions):
        self.functions = functions


def test_token_analyzer_reads_erc20_metadata(monkeypatch):
    functions = FakeFunctions()

    monkeypatch.setattr(
        token_module.w3.eth,
        "contract",
        lambda **_: FakeContract(functions),
    )

    result = token_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    data = result["data"]

    assert result["success"] is True
    assert data["name"] == "Example Token"
    assert data["symbol"] == "EXT"
    assert data["decimals"] == 18
    assert data["total_supply_raw"] == 1_000_000 * 10**18
    assert data["total_supply"] == 1_000_000


def test_token_analyzer_allows_partial_metadata_failure(monkeypatch):
    functions = FakeFunctions()

    functions.symbol = FakeFunction(
        error=RuntimeError("symbol unavailable")
    )

    monkeypatch.setattr(
        token_module.w3.eth,
        "contract",
        lambda **_: FakeContract(functions),
    )

    result = token_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    data = result["data"]

    assert result["success"] is True
    assert data["name"] == "Example Token"
    assert data["symbol"] is None
    assert data["decimals"] == 18
    assert data["total_supply"] == 1_000_000


def test_token_analyzer_does_not_normalize_supply_without_decimals(
    monkeypatch,
):
    functions = FakeFunctions(decimals=None)

    monkeypatch.setattr(
        token_module.w3.eth,
        "contract",
        lambda **_: FakeContract(functions),
    )

    result = token_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    data = result["data"]

    assert data["decimals"] is None
    assert data["total_supply_raw"] is not None
    assert data["total_supply"] is None


def test_token_analyzer_returns_unknown_on_invalid_address():
    result = token_module.analyze("not-an-address")

    assert result["success"] is False
    assert result["data"] == {}
    assert result["error"]


def test_token_analyzer_returns_unknown_on_contract_creation_failure(
    monkeypatch,
):
    def fail_contract(**_):
        raise RuntimeError("contract creation failed")

    monkeypatch.setattr(
        token_module.w3.eth,
        "contract",
        fail_contract,
    )

    result = token_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is False
    assert result["data"] == {}
    assert "contract creation failed" in result["error"]


def test_token_analyzer_uses_cache_without_rpc(monkeypatch):
    import json

    result_payload = {
        "success": True,
        "source": "token",
        "data": {
            "address": "0x0000000000000000000000000000000000000001",
            "name": "Cached Token",
            "symbol": "CACHE",
            "decimals": 18,
            "total_supply_raw": 1000,
            "total_supply": 0.000000000000001,
        },
    }

    monkeypatch.setattr(
        token_module._cache,
        "get",
        lambda *args, **kwargs: json.dumps(result_payload),
    )

    def fail_contract(**_):
        raise AssertionError("RPC/contract should not be called")

    monkeypatch.setattr(
        token_module.w3.eth,
        "contract",
        fail_contract,
    )

    result = token_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result == result_payload


def test_token_analyzer_writes_success_to_cache(monkeypatch):
    writes = []

    monkeypatch.setattr(
        token_module._cache,
        "get",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        token_module._cache,
        "set",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )

    class FakeCall:
        def __init__(self, value):
            self.value = value

        def call(self):
            return self.value

    class FakeFunctions:
        def name(self):
            return FakeCall("Example")

        def symbol(self):
            return FakeCall("EX")

        def decimals(self):
            return FakeCall(18)

        def totalSupply(self):
            return FakeCall(10**18)

    class FakeContract:
        functions = FakeFunctions()

    monkeypatch.setattr(
        token_module.w3.eth,
        "contract",
        lambda **_: FakeContract(),
    )

    result = token_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is True
    assert len(writes) == 1


def test_token_analyzer_does_not_cache_boundary_failure(monkeypatch):
    writes = []

    monkeypatch.setattr(
        token_module._cache,
        "get",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        token_module._cache,
        "set",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )

    def fail_contract(**_):
        raise RuntimeError("contract failed")

    monkeypatch.setattr(
        token_module.w3.eth,
        "contract",
        fail_contract,
    )

    result = token_module.analyze(
        "0x0000000000000000000000000000000000000001"
    )

    assert result["success"] is False
    assert writes == []
