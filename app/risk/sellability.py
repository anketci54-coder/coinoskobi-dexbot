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
from app.dex.lp_security import (
    analyze as lp_security_analyze,
)
from app.risk.exit_feasibility import (
    analyze as exit_feasibility_analyze,
)


_cache = AnalyzerCache()


def _base_unknown():
    return {
        "honeypot": None,
        "sellable": None,

        "sellability_checked": False,

        "sellability_provider": (
            "honeypot.is"
        ),

        "simulation_success": None,
        "simulation_error": None,

        "honeypot_reason": None,

        "provider_risk": None,
        "provider_risk_level": None,

        "buy_tax": None,
        "sell_tax": None,
        "transfer_tax": None,

        "buy_gas": None,
        "sell_gas": None,
    }


def _local_evidence(
    token,
    pair,
):
    if not pair:
        return {
            "completed": False,

            "lp_security": None,

            "exit_feasibility": None,

            "lp_error": None,
            "exit_error": None,

            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    lp = lp_security_analyze(
        pair
    )

    exit_result = (
        exit_feasibility_analyze(
            token,
            pair,
        )
    )

    exit_data = (
        exit_result.get("data")
        or {}
    )

    return {
        "completed": bool(
            lp.get("success")
            and exit_result.get(
                "success"
            )
            and exit_data.get(
                "evidence_complete"
            )
        ),

        "lp_security": (
            lp.get("data")
            or {}
        ),

        "exit_feasibility": (
            exit_data
        ),

        "lp_error": (
            lp.get("error")
        ),

        "exit_error": (
            exit_result.get("error")
        ),

        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _parse_payload(payload):
    honeypot_result = (
        payload.get(
            "honeypotResult"
        )
        or {}
    )

    simulation = (
        payload.get(
            "simulationResult"
        )
        or {}
    )

    summary = (
        payload.get("summary")
        or {}
    )

    simulation_success = (
        payload.get(
            "simulationSuccess"
        )
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
        and simulation_success
        is True
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
            summary.get(
                "riskLevel"
            )
        ),

        "buy_tax": (
            simulation.get(
                "buyTax"
            )
        ),

        "sell_tax": (
            simulation.get(
                "sellTax"
            )
        ),

        "transfer_tax": (
            simulation.get(
                "transferTax"
            )
        ),

        "buy_gas": (
            simulation.get(
                "buyGas"
            )
        ),

        "sell_gas": (
            simulation.get(
                "sellGas"
            )
        ),
    }


def _analyze_provider_once(
    address,
    *,
    pair=None,
    simulate_liquidity=False,
):
    try:
        token = (
            Web3.to_checksum_address(
                address
            )
        )

    except Exception as exc:
        data = _base_unknown()

        data[
            "local_evidence"
        ] = _local_evidence(
            address,
            None,
        )

        return {
            "success": False,
            "provider_success": False,
            "source": "sellability",
            "error": str(exc),
            "data": data,
        }

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
            ):
                return cached_result

        except Exception:
            pass

    local = _local_evidence(
        token,
        pair,
    )

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

    provider_success = False
    provider_error = None
    provider_status_code = None

    data = _base_unknown()

    try:
        response = requests.get(
            HONEYPOT_API_URL,
            params=params,
            timeout=(
                SELLABILITY_HTTP_TIMEOUT_SECONDS
            ),
        )

        provider_status_code = getattr(
            response,
            "status_code",
            None,
        )

        response.raise_for_status()

        data.update(
            _parse_payload(
                response.json()
            )
        )

        provider_success = True

    except Exception as exc:
        provider_error = str(exc)

    data[
        "local_evidence"
    ] = local

    data.update({
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    })

    result = {
        "success": bool(
            provider_success
        ),

        "provider_success": (
            provider_success
        ),

        "provider_status_code": (
            provider_status_code
        ),

        "local_evidence_complete": bool(
            local.get(
                "completed"
            )
        ),

        "source": "sellability",

        "error": provider_error,

        "data": data,
    }

    if provider_success:
        try:
            _cache.set(
                "sellability",
                cache_key,
                json.dumps(
                    result,
                    default=str,
                ),
            )

        except Exception:
            pass

    return result
# SELLABILITY_PROVIDER_FALLBACK_V2


def _provider_verified(
    result,
):
    return bool(
        isinstance(
            result,
            dict,
        )
        and result.get(
            "provider_success"
        )
        is True
        and result.get(
            "success"
        )
        is True
    )


def _provider_404(
    result,
):
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


def _fallback_metadata(
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
        ] = str(
            pair_error
        )

    if token_error:
        data[
            "provider_token_error"
        ] = str(
            token_error
        )

    result["data"] = data

    return result


def analyze(
    address,
    *,
    pair=None,
):
    """
    Provider-backed sellability chain.

    pair
      -> HTTP 404 only: token-only
      -> HTTP 404 only: simulateLiquidity=true

    Provider/network failure remains UNKNOWN.

    Local evidence remains available to mathematical
    planning and risk analysis but cannot independently
    create SELLABILITY_OK.
    """

    first = _analyze_provider_once(
        address,
        pair=pair,
    )

    if _provider_verified(
        first
    ):
        return first

    if (
        not pair
        or not _provider_404(
            first
        )
    ):
        return first

    pair_error = (
        first.get("error")
        if isinstance(
            first,
            dict,
        )
        else None
    )

    token_only = (
        _analyze_provider_once(
            address,
            pair=None,
        )
    )

    if _provider_verified(
        token_only
    ):
        return _fallback_metadata(
            token_only,
            mode="TOKEN_ONLY",
            pair_error=pair_error,
        )

    if not _provider_404(
        token_only
    ):
        return _fallback_metadata(
            token_only,
            mode="TOKEN_ONLY_FAILED",
            pair_error=pair_error,
        )

    token_error = (
        token_only.get("error")
        if isinstance(
            token_only,
            dict,
        )
        else None
    )

    simulated = (
        _analyze_provider_once(
            address,
            pair=None,
            simulate_liquidity=True,
        )
    )

    return _fallback_metadata(
        simulated,
        mode="SIMULATE_LIQUIDITY",
        pair_error=pair_error,
        token_error=token_error,
    )
