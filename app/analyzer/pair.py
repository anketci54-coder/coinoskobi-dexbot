from web3 import Web3

from app.chains.bsc import w3
from app.config.contracts import PANCAKE_FACTORY
from app.config.abis.factory_full import FACTORY_ABI
from app.config.abis.pair import PAIR_ABI
from app.config.contracts import WBNB

factory = w3.eth.contract(
    address=Web3.to_checksum_address(PANCAKE_FACTORY),
    abi=FACTORY_ABI
)


def analyze(token):

    pair = factory.functions.getPair(
        Web3.to_checksum_address(token),
        Web3.to_checksum_address(WBNB)
    ).call()

    if pair == "0x0000000000000000000000000000000000000000":

        return {
            "success": True,
            "source": "pair",
            "data": {
                "exists": False,
                "pair": None,
                "token0": None,
                "token1": None,
                "reserve0": 0,
                "reserve1": 0,
                "quote_ok": False
            }
        }

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(pair),
        abi=PAIR_ABI
    )

    token0 = contract.functions.token0().call()
    token1 = contract.functions.token1().call()

    reserves = contract.functions.getReserves().call()

    return {
        "success": True,
        "source": "pair",
        "data": {
            "exists": True,
            "pair": pair,
            "token0": token0,
            "token1": token1,
            "reserve0": reserves[0],
            "reserve1": reserves[1],
            "quote_ok": True
        }
    }


if __name__ == "__main__":

    token = input("Token : ").strip()

    print(analyze(token))
