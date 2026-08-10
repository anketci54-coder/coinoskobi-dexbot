import json

from web3 import Web3

from app.chains.bsc import w3
from app.cache.analyzer_cache import AnalyzerCache
from app.config.scanner import RISK_ANALYZER_CACHE_TTL_SECONDS


_cache = AnalyzerCache()

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
    "max_wallet": "70480275",
}


def analyze(address):
    try:
        checksum_address = Web3.to_checksum_address(address)
    except Exception as exc:
        return {
            "success": False,
            "source": "risk",
            "error": str(exc),
            "data": {},
        }

    cache_key = f"bsc:{checksum_address.lower()}"

    try:
        cached = _cache.get(
            "risk",
            cache_key,
            ttl_seconds=RISK_ANALYZER_CACHE_TTL_SECONDS,
        )
    except Exception:
        cached = None

    if cached is not None:
        try:
            return json.loads(cached)
        except Exception:
            pass

    try:
        code = w3.eth.get_code(checksum_address).hex()
    except Exception as exc:
        return {
            "success": False,
            "source": "risk",
            "error": str(exc),
            "data": {},
        }

    result = {
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
            "max_wallet": SIGNATURES["max_wallet"] in code,
        },
    }

    try:
        _cache.set(
            "risk",
            cache_key,
            json.dumps(result),
        )
    except Exception:
        pass

    return result


if __name__ == "__main__":
    token = input("Token : ").strip()
    print(analyze(token))
