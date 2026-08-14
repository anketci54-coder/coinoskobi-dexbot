from app.dex.pair_membership import verify_pair_membership


class Call:
    def __init__(self, value):
        self.value = value

    def call(self):
        return self.value


class Functions:
    def __init__(self, pair, token0, token1):
        self.pair = pair
        self._token0 = token0
        self._token1 = token1

    def getPair(self, *_):
        return Call(self.pair)

    def token0(self):
        return Call(self._token0)

    def token1(self):
        return Call(self._token1)


class Eth:
    def __init__(self, pair, token0, token1):
        self.values = (pair, token0, token1)

    def contract(self, address=None, abi=None):
        return type("Contract", (), {
            "functions": Functions(*self.values),
        })()


class Client:
    def __init__(self, pair, token0, token1):
        self.eth = Eth(pair, token0, token1)


def test_pair_membership_verified():
    pair = "0x" + "11" * 20
    token = "0x" + "22" * 20
    quote = "0x" + "33" * 20

    result = verify_pair_membership(
        pair,
        token,
        quote,
        client=Client(pair, token, quote),
    )

    assert result["state"] == "VERIFIED"


def test_pair_membership_rejects_factory_mismatch():
    pair = "0x" + "11" * 20
    other = "0x" + "44" * 20
    token = "0x" + "22" * 20
    quote = "0x" + "33" * 20

    result = verify_pair_membership(
        pair,
        token,
        quote,
        client=Client(other, token, quote),
    )

    assert result["state"] == "FACTORY_MISMATCH"
