import app.risk.exit_feasibility as module


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
