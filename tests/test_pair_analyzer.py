import app.analyzer.pair as pair_module


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
