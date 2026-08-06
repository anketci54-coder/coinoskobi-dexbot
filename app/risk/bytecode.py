from web3 import Web3

from app.chains.bsc import w3

SIGNATURES = {
    "owner()": "8da5cb5b",
    "transferOwnership(address)": "f2fde38b",
    "renounceOwnership()": "715018a6",
    "pause()": "8456cb59",
    "unpause()": "3f4ba83a",
    "mint(address,uint256)": "40c10f19",
    "burn(uint256)": "42966c68",
    "blacklist(address)": "f9f92be4",
    "setBlacklist(address,bool)": "6c19e783",
    "excludeFromFees(address,bool)": "0e0e6d84",
    "setMaxTxAmount(uint256)": "ec28438a",
    "setMaxWalletSize(uint256)": "70480275"
}


def analyze(address):

    code = w3.eth.get_code(Web3.to_checksum_address(address)).hex()

    print()
    print("Contract Size :", len(code) // 2, "bytes")
    print()

    for name, selector in SIGNATURES.items():

        found = selector.lower() in code.lower()

        print(f"{name:<35} {'YES' if found else 'NO'}")


if __name__ == "__main__":

    token = input("Token : ").strip()

    analyze(token)
