import json

from web3 import Web3

from app.chains.bsc import w3
from app.cache.analyzer_cache import AnalyzerCache
from app.config.contracts import PANCAKE_FACTORY, WBNB
from app.config.scanner import PAIR_ANALYZER_CACHE_TTL_SECONDS
from app.config.abis.factory_full import FACTORY_ABI


_cache = AnalyzerCache()

factory = w3.eth.contract(
    address=Web3.to_checksum_address(PANCAKE_FACTORY),
    abi=FACTORY_ABI,
)

ZERO = "0x0000000000000000000000000000000000000000"


def analyze(token):
    try:
        checksum_token = Web3.to_checksum_address(token)
        checksum_wbnb = Web3.to_checksum_address(WBNB)
    except Exception as exc:
        return {
            "success": False,
            "source": "pair",
            "error": str(exc),
            "data": {},
        }

    cache_key = f"bsc:{checksum_token.lower()}"

    try:
        cached = _cache.get(
            "pair",
            cache_key,
            ttl_seconds=PAIR_ANALYZER_CACHE_TTL_SECONDS,
        )
    except Exception:
        cached = None

    if cached is not None:
        try:
            return json.loads(cached)
        except Exception:
            pass

    try:
        pair = factory.functions.getPair(
            checksum_token,
            checksum_wbnb,
        ).call()
    except Exception as exc:
        return {
            "success": False,
            "source": "pair",
            "error": str(exc),
            "data": {},
        }

    exists = pair != ZERO

    result = {
        "success": True,
        "source": "pair",
        "data": {
            "exists": exists,
            "pair": pair if exists else None,
            "quote_ok": exists,
        },
    }

    try:
        _cache.set(
            "pair",
            cache_key,
            json.dumps(result),
        )
    except Exception:
        pass

    return result


if __name__ == "__main__":
    token = input("Token : ").strip()
    print(analyze(token))
