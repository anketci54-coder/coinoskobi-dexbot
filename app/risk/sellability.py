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


def _unknown(
    error,
    *,
    status_code=None,
):
    return {
        "success": False,
        "provider_success": False,
        "provider_status_code": status_code,
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


def _request_once(
    address,
    *,
    pair=None,
    simulate_liquidity=False,
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

    if simulate_liquidity:
        cache_key = (
            f"{cache_key}:simulate_liquidity"
        )

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
            cached_result = json.loads(
                cached
            )

            if (
                cached_result.get(
                    "provider_success"
                )
                is True
                or (
                    "provider_success"
                    not in cached_result
                    and cached_result.get(
                        "success"
                    )
                    is True
                )
            ):
                return cached_result

        except Exception:
            pass

    params = {
        "address": token,
        "chainID": BSC_CHAIN_ID,
    }

    if pair:
        params["pair"] = pair

    if simulate_liquidity:
        params[
            "simulateLiquidity"
        ] = "true"

    try:
        response = requests.get(
            HONEYPOT_API_URL,
            params=params,
            timeout=(
                SELLABILITY_HTTP_TIMEOUT_SECONDS
            ),
        )

        status_code = getattr(
            response,
            "status_code",
            None,
        )

        response.raise_for_status()

        data = _parse_payload(
            response.json()
        )

    except Exception as exc:
        response = getattr(
            exc,
            "response",
            None,
        )

        status_code = getattr(
            response,
            "status_code",
            None,
        )

        return _unknown(
            exc,
            status_code=status_code,
        )

    result = {
        "success": True,
        "provider_success": True,
        "provider_status_code": status_code,
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


def _provider_404(result):
    if not isinstance(
        result,
        dict,
    ):
        return False

    if (
        result.get(
            "provider_status_code"
        )
        == 404
    ):
        return True

    return (
        "404"
        in str(
            result.get("error")
            or ""
        )
    )


def _with_fallback_metadata(
    result,
    *,
    mode,
    pair_error=None,
    token_error=None,
):
    if not isinstance(
        result,
        dict,
    ):
        return result

    result = dict(result)

    data = dict(
        result.get("data")
        or {}
    )

    data[
        "provider_fallback_mode"
    ] = mode

    if pair_error:
        data[
            "provider_pair_error"
        ] = str(pair_error)

    if token_error:
        data[
            "provider_token_error"
        ] = str(token_error)

    result["data"] = data

    return result


def analyze(
    address,
    *,
    pair=None,
):
    """Return provider-backed sellability evidence.

    Provider failures remain UNKNOWN. Pair-specific HTTP 404 is retried once
    token-only; a second HTTP 404 is retried with simulateLiquidity=true.
    No failure path is converted into verified sellability.
    """

    first = _request_once(
        address,
        pair=pair,
    )

    if first.get("success") is True:
        return first

    if (
        not pair
        or not _provider_404(
            first
        )
    ):
        return first

    pair_error = first.get("error")

    token_only = _request_once(
        address,
        pair=None,
    )

    if token_only.get("success") is True:
        return _with_fallback_metadata(
            token_only,
            mode="TOKEN_ONLY",
            pair_error=pair_error,
        )

    if not _provider_404(
        token_only
    ):
        return _with_fallback_metadata(
            token_only,
            mode="TOKEN_ONLY_FAILED",
            pair_error=pair_error,
        )

    simulated = _request_once(
        address,
        pair=None,
        simulate_liquidity=True,
    )

    return _with_fallback_metadata(
        simulated,
        mode="SIMULATE_LIQUIDITY",
        pair_error=pair_error,
        token_error=(
            token_only.get("error")
        ),
    )
