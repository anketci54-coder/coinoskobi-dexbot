from web3 import Web3

from app.chains.bsc import w3


ERC20_METADATA_ABI = [
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def _safe_call(contract, function_name):
    try:
        function = getattr(contract.functions, function_name)
        return function().call()
    except Exception:
        return None


def analyze(address):
    try:
        checksum_address = Web3.to_checksum_address(address)

        contract = w3.eth.contract(
            address=checksum_address,
            abi=ERC20_METADATA_ABI,
        )
    except Exception as exc:
        return {
            "success": False,
            "source": "token",
            "error": str(exc),
            "data": {},
        }

    name = _safe_call(contract, "name")
    symbol = _safe_call(contract, "symbol")
    decimals = _safe_call(contract, "decimals")
    total_supply_raw = _safe_call(contract, "totalSupply")

    total_supply = None

    if (
        total_supply_raw is not None
        and decimals is not None
        and isinstance(decimals, int)
        and 0 <= decimals <= 255
    ):
        total_supply = total_supply_raw / (10 ** decimals)

    return {
        "success": True,
        "source": "token",
        "data": {
            "address": checksum_address,
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "total_supply_raw": total_supply_raw,
            "total_supply": total_supply,
        },
    }


if __name__ == "__main__":
    token = input("Token : ").strip()
    print(analyze(token))
