from web3 import Web3

from app.chains.bsc import w3
from app.config.abis.erc20 import ERC20_ABI


def analyze(address):

    token = w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=ERC20_ABI
    )

    try:
        name = token.functions.name().call()
    except:
        name = "?"

    try:
        symbol = token.functions.symbol().call()
    except:
        symbol = "?"

    try:
        decimals = token.functions.decimals().call()
    except:
        decimals = 0

    try:
        supply = token.functions.totalSupply().call()

        if decimals > 0:
            supply = supply / (10 ** decimals)

    except:
        supply = 0

    return {
        "success": True,
        "source": "token",
        "data": {
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "supply": supply
        }
    }


if __name__ == "__main__":

    addr = input("Token : ").strip()

    info = analyze(addr)["data"]

    print()
    print("Name      :", info["name"])
    print("Symbol    :", info["symbol"])
    print("Decimals  :", info["decimals"])
    print("Supply    :", info["supply"])
