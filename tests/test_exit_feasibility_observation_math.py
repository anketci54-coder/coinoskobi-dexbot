import app.risk.exit_feasibility as module
import pytest


TOKEN = "0x1111111111111111111111111111111111111111"
PAIR = "0x2222222222222222222222222222222222222222"


class Call:
    def __init__(self, fn):
        self.fn = fn

    def call(self, *args, **kwargs):
        return self.fn(*args, **kwargs)


class PairFunctions:
    def token0(self):
        return Call(lambda: TOKEN)

    def token1(self):
        return Call(lambda: module.WBNB)

    def getReserves(self):
        def value(*args, **kwargs):
            block = kwargs.get("block_identifier")
            if block == 90:
                return (1000 * 10**18, 20 * 10**18, 0)
            if block == 95:
                return (1000 * 10**18, 18 * 10**18, 0)
            return (1000 * 10**18, 19 * 10**18, 0)

        return Call(value)


class TokenFunctions:
    def decimals(self):
        return Call(lambda: 18)


class RouterFunctions:
    def getAmountsOut(self, amount_in, path):
        if path[0].lower() == module.WBNB.lower():
            return Call(
                lambda: [amount_in, 600 * 10**18]
            )

        reserve_in = 1000.0
        reserve_out = 19.0
        gross_in = amount_in / 10**18
        fee = 0.0025
        effective = gross_in * (1.0 - fee)
        out = (
            reserve_out * effective
            / (reserve_in + effective)
        )

        return Call(
            lambda: [amount_in, int(out * 10**18)]
        )


class Contract:
    def __init__(self, functions):
        self.functions = functions


class Eth:
    block_number = 100
    gas_price = 3_000_000_000

    def contract(self, address, abi):
        lower = address.lower()

        if lower == PAIR.lower():
            return Contract(PairFunctions())

        if lower == TOKEN.lower():
            return Contract(TokenFunctions())

        return Contract(RouterFunctions())


class FakeW3:
    eth = Eth()


def test_exit_feasibility_exposes_measured_reserve_floor_and_fee(
    monkeypatch,
):
    monkeypatch.setattr(module, "w3", FakeW3())
    monkeypatch.setattr(
        module,
        "RESERVE_HISTORY_BLOCK_OFFSETS",
        (10, 5, 0),
    )

    result = module.analyze(TOKEN, PAIR)

    assert result["success"] is True

    data = result["data"]

    assert data["reserve_observation_count"] == 3
    assert data["quote_reserve_usd"] == 19 * 600
    assert (
        data["observed_min_quote_reserve_usd"]
        == 18 * 600
    )
    assert abs(
        data["reserve_floor_fraction_of_current"]
        - (18 / 19)
    ) < 1e-12

    assert data["implied_v2_fee_state"] == "READY"
    assert abs(
        data["implied_v2_fee_fraction"] - 0.0025
    ) < 1e-9

    assert data["trade_authority"] is False
    assert data["execution_authority"] is False


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("decimals", [(18, 6), (6, 18)])
def test_usdt_exit_evidence_uses_pair_orientation_and_quote_decimals(monkeypatch, reverse, decimals):
    token_decimals, quote_decimals = decimals
    class Pair(PairFunctions):
        def token0(self):
            return Call(lambda: module.USDT if reverse else TOKEN)
        def token1(self):
            return Call(lambda: TOKEN if reverse else module.USDT)
        def getReserves(self):
            reserves = (1000 * 10**token_decimals, 2000 * 10**quote_decimals)
            return Call(lambda **kw: (*(reserves[::-1] if reverse else reserves), 0))
    class Asset:
        def __init__(self, decimals):
            self.value = decimals
        def decimals(self):
            return Call(lambda: self.value)
    class Router:
        def getAmountsOut(self, amount, path):
            if path[0].lower() == module.WBNB.lower():
                return Call(lambda: [amount, 600 * 10**18])
            assert path[-1].lower() == module.USDT.lower()
            return Call(lambda: [amount, int(2000 * .9975 / (1000 + .9975) * 10**quote_decimals)])
    class StableEth(Eth):
        def contract(self, address, abi):
            functions = (Pair() if address.lower() == PAIR else
                         Asset(token_decimals) if address.lower() == TOKEN else
                         Asset(quote_decimals) if address.lower() == module.USDT.lower() else Router())
            return Contract(functions)
    monkeypatch.setattr(module, "w3", type("RPC", (), {"eth": StableEth()})())
    monkeypatch.setattr(module, "RESERVE_HISTORY_BLOCK_OFFSETS", (10, 5, 0))
    result = module.analyze(TOKEN, PAIR)
    assert result["success"] is True, result["error"]
    data = result["data"]
    assert data["spot_price_series_usd"] == [2, 2, 2]
    assert data["quote_reserve_usd"] == 2000
    assert data["quote_token"].lower() == module.USDT.lower()
    assert data["implied_v2_fee_fraction"] == pytest.approx(.0025, abs=1e-6)


def test_missing_current_block_cannot_publish_old_price_as_fresh(monkeypatch):
    class MissingLatest(PairFunctions):
        def getReserves(self):
            def read(**kw):
                if kw.get("block_identifier") == 100:
                    raise ConnectionError("latest unavailable")
                return (1000 * 10**18, 20 * 10**18, 0)
            return Call(read)
    class MissingEth(Eth):
        def contract(self, address, abi):
            if address.lower() == PAIR:
                return Contract(MissingLatest())
            return super().contract(address, abi)
    monkeypatch.setattr(module, "w3", type("RPC", (), {"eth": MissingEth()})())
    monkeypatch.setattr(module, "RESERVE_HISTORY_BLOCK_OFFSETS", (10, 5, 0))
    module._RUNTIME_PAIR_PRICE_HISTORY.clear()
    result = module.analyze(TOKEN, PAIR)
    assert result["data"]["evidence_complete"] is False
    assert result["data"]["runtime_spot_price_series_usd"] == []
    assert module._RUNTIME_PAIR_PRICE_HISTORY == {}
