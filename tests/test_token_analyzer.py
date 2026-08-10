import app.analyzer.token as token_module


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
