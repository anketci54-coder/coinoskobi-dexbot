from web3 import Web3

from app.chains.bsc import w3
from app.config.contracts import PANCAKE_FACTORY, WBNB
from app.config.abis.factory_full import FACTORY_ABI


factory = w3.eth.contract(
    address=Web3.to_checksum_address(PANCAKE_FACTORY),
    abi=FACTORY_ABI,
)

ZERO = "0x0000000000000000000000000000000000000000"


def analyze(token):
    try:
        pair = factory.functions.getPair(
            Web3.to_checksum_address(token),
            Web3.to_checksum_address(WBNB),
        ).call()
    except Exception as exc:
        return {
            "success": False,
            "source": "pair",
            "error": str(exc),
            "data": {},
        }

    exists = pair != ZERO

    return {
        "success": True,
        "source": "pair",
        "data": {
            "exists": exists,
            "pair": pair if exists else None,
            "quote_ok": exists,
        },
    }


if __name__ == "__main__":
    token = input("Token : ").strip()
    print(analyze(token))
