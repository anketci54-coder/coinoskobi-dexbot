from web3 import Web3

from app.chains.bsc import w3

SIGNATURES = {
    "owner": "8da5cb5b",
    "transferOwnership": "f2fde38b",
    "renounceOwnership": "715018a6",
    "pause": "8456cb59",
    "unpause": "3f4ba83a",
    "mint": "40c10f19",
    "burn": "42966c68",
    "blacklist": "f9f92be4",
    "setBlacklist": "6c19e783",
    "excludeFromFees": "0e0e6d84",
    "max_tx": "ec28438a",
    "max_wallet": "70480275"
}


def analyze(address):

    code = w3.eth.get_code(
        Web3.to_checksum_address(address)
    ).hex()

    return {
        "success": True,
        "source": "risk",
        "data": {
            "code_size": len(code) // 2,
            "owner": SIGNATURES["owner"] in code,
            "transfer_owner": SIGNATURES["transferOwnership"] in code,
            "renounce_owner": SIGNATURES["renounceOwnership"] in code,
            "pause": SIGNATURES["pause"] in code,
            "unpause": SIGNATURES["unpause"] in code,
            "mint": SIGNATURES["mint"] in code,
            "burn": SIGNATURES["burn"] in code,
            "blacklist": SIGNATURES["blacklist"] in code,
            "set_blacklist": SIGNATURES["setBlacklist"] in code,
            "exclude_fee": SIGNATURES["excludeFromFees"] in code,
            "max_tx": SIGNATURES["max_tx"] in code,
            "max_wallet": SIGNATURES["max_wallet"] in code
        }
    }


if __name__ == "__main__":

    token = input("Token : ").strip()

    print(analyze(token))
