from web3 import Web3

from app.chains.bsc import w3
from app.config.abis.factory_full import FACTORY_ABI
from app.config.contracts import PANCAKE_FACTORY


PAIR_ABI = [
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def verify_pair_membership(pair, token, quote_token, client=None):
    client = client or w3

    try:
        pair = Web3.to_checksum_address(pair)
        token = Web3.to_checksum_address(token)
        quote = Web3.to_checksum_address(quote_token)

        factory = client.eth.contract(
            address=Web3.to_checksum_address(PANCAKE_FACTORY),
            abi=FACTORY_ABI,
        )

        canonical = factory.functions.getPair(token, quote).call()

        if canonical.lower() != pair.lower():
            return {"state": "FACTORY_MISMATCH"}

        contract = client.eth.contract(address=pair, abi=PAIR_ABI)
        token0 = contract.functions.token0().call()
        token1 = contract.functions.token1().call()

        if {token0.lower(), token1.lower()} != {
            token.lower(),
            quote.lower(),
        }:
            return {"state": "TOKEN_MISMATCH"}

        return {
            "state": "VERIFIED",
            "pair": pair.lower(),
            "token0": token0.lower(),
            "token1": token1.lower(),
            "decision_authority": False,
            "execution_authority": False,
        }

    except Exception as exc:
        return {
            "state": "UNKNOWN",
            "error": f"{type(exc).__name__}: {exc}",
        }
