import json

import requests
from web3 import Web3

from app.cache.analyzer_cache import (
    AnalyzerCache,
)
from app.config.strategy import (
    BSC_CHAIN_ID,
    HONEYPOT_API_URL,
    SELLABILITY_CACHE_TTL_SECONDS,
    SELLABILITY_HTTP_TIMEOUT_SECONDS,
)


_cache = AnalyzerCache()


def _unknown(error):
    return {
        "success": False,
        "source": "sellability",
        "error": str(error),
        "data": {
            "honeypot": None,
            "sellable": None,
            "sellability_checked": False,
            "sellability_provider": (
                "honeypot.is"
            ),
        },
    }


def _parse_payload(payload):
    honeypot_result = (
        payload.get("honeypotResult")
        or {}
    )

    simulation = (
        payload.get("simulationResult")
        or {}
    )

    summary = (
        payload.get("summary")
        or {}
    )

    simulation_success = (
        payload.get("simulationSuccess")
    )

    is_honeypot = (
        honeypot_result.get(
            "isHoneypot"
        )
    )

    # Strict semantics:
    #
    # Honeypot TRUE is explicit evidence.
    #
    # Sellable TRUE requires:
    # - successful simulation
    # - explicit non-honeypot result
    #
    # Anything else stays UNKNOWN.
    if is_honeypot is True:
        sellable = False

    elif (
        is_honeypot is False
        and simulation_success is True
    ):
        sellable = True

    else:
        sellable = None

    return {
        "honeypot": (
            True
            if is_honeypot is True
            else (
                False
                if is_honeypot is False
                else None
            )
        ),
        "sellable": sellable,
        "sellability_checked": True,
        "sellability_provider": (
            "honeypot.is"
        ),
        "simulation_success": (
            simulation_success
        ),
        "simulation_error": (
            payload.get(
                "simulationError"
            )
        ),
        "honeypot_reason": (
            honeypot_result.get(
                "honeypotReason"
            )
        ),
        "provider_risk": (
            summary.get("risk")
        ),
        "provider_risk_level": (
            summary.get("riskLevel")
        ),
        "buy_tax": (
            simulation.get("buyTax")
        ),
        "sell_tax": (
            simulation.get("sellTax")
        ),
        "transfer_tax": (
            simulation.get(
                "transferTax"
            )
        ),
        "buy_gas": (
            simulation.get("buyGas")
        ),
        "sell_gas": (
            simulation.get("sellGas")
        ),
    }


def analyze(
    address,
    *,
    pair=None,
):
    try:
        token = Web3.to_checksum_address(
            address
        )
    except Exception as exc:
        return _unknown(exc)

    cache_key = (
        f"bsc:{token.lower()}"
    )

    if pair:
        try:
            pair = (
                Web3.to_checksum_address(
                    pair
                )
            )

            cache_key = (
                f"{cache_key}:"
                f"{pair.lower()}"
            )

        except Exception:
            pair = None

    try:
        cached = _cache.get(
            "sellability",
            cache_key,
            ttl_seconds=(
                SELLABILITY_CACHE_TTL_SECONDS
            ),
        )
    except Exception:
        cached = None

    if cached is not None:
        try:
            return json.loads(cached)
        except Exception:
            pass

    params = {
        "address": token,
        "chainID": BSC_CHAIN_ID,
    }

    if pair:
        params["pair"] = pair

    try:
        response = requests.get(
            HONEYPOT_API_URL,
            params=params,
            timeout=(
                SELLABILITY_HTTP_TIMEOUT_SECONDS
            ),
        )

        response.raise_for_status()

        payload = response.json()

    except Exception as exc:
        # Provider/network failure is UNKNOWN.
        # Never classify it as a honeypot.
        return _unknown(exc)

    data = _parse_payload(
        payload
    )

    result = {
        "success": True,
        "source": "sellability",
        "error": None,
        "data": data,
    }

    try:
        _cache.set(
            "sellability",
            cache_key,
            json.dumps(result),
        )
    except Exception:
        pass

    return result
