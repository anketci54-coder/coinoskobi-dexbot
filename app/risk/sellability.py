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


GOPLUS_TOKEN_SECURITY_URL = (
    "https://api.gopluslabs.io/api/v1/token_security"
)

_cache = AnalyzerCache()


def _base_unknown():
    return {
        "honeypot": None,
        "sellable": None,
        "sellability_checked": False,
        "sellability_provider": "honeypot.is",
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


def _local_evidence(token, pair):
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

    lp = lp_security_analyze(pair)
    exit_result = exit_feasibility_analyze(token, pair)
    exit_data = exit_result.get("data") or {}

    return {
        "completed": bool(
            lp.get("success")
            and exit_result.get("success")
            and exit_data.get("evidence_complete")
        ),
        "lp_security": lp.get("data") or {},
        "exit_feasibility": exit_data,
        "lp_error": lp.get("error"),
        "exit_error": exit_result.get("error"),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _parse_payload(payload):
    honeypot_result = payload.get("honeypotResult") or {}
    simulation = payload.get("simulationResult") or {}
    summary = payload.get("summary") or {}
    simulation_success = payload.get("simulationSuccess")
    is_honeypot = honeypot_result.get("isHoneypot")

    if is_honeypot is True:
        sellable = False
    elif is_honeypot is False and simulation_success is True:
        sellable = True
    else:
        sellable = None

    return {
        "honeypot": (
            True
            if is_honeypot is True
            else False
            if is_honeypot is False
            else None
        ),
        "sellable": sellable,
        "sellability_checked": True,
        "sellability_provider": "honeypot.is",
        "simulation_success": simulation_success,
        "simulation_error": payload.get("simulationError"),
        "honeypot_reason": honeypot_result.get("honeypotReason"),
        "provider_risk": summary.get("risk"),
        "provider_risk_level": summary.get("riskLevel"),
        "buy_tax": simulation.get("buyTax"),
        "sell_tax": simulation.get("sellTax"),
        "transfer_tax": simulation.get("transferTax"),
        "buy_gas": simulation.get("buyGas"),
        "sell_gas": simulation.get("sellGas"),
    }


def _analyze_provider_once(
    address,
    *,
    pair=None,
    simulate_liquidity=False,
):
    try:
        token = Web3.to_checksum_address(address)
    except Exception as exc:
        data = _base_unknown()
        data["local_evidence"] = _local_evidence(address, None)
        return {
            "success": False,
            "provider_success": False,
            "source": "sellability",
            "error": str(exc),
            "data": data,
        }

    cache_key = f"bsc:{token.lower()}"

    if pair:
        try:
            pair = Web3.to_checksum_address(pair)
            cache_key = f"{cache_key}:{pair.lower()}"
        except Exception:
            pair = None

    if simulate_liquidity:
        cache_key = f"{cache_key}:simulate_liquidity"

    try:
        cached = _cache.get(
            "sellability",
            cache_key,
            ttl_seconds=SELLABILITY_CACHE_TTL_SECONDS,
        )
    except Exception:
        cached = None

    if cached is not None:
        try:
            cached_result = json.loads(cached)
            if cached_result.get("provider_success") is True:
                return cached_result
        except Exception:
            pass

    local = _local_evidence(token, pair)
    params = {
        "address": token,
        "chainID": BSC_CHAIN_ID,
    }

    if pair:
        params["pair"] = pair

    if simulate_liquidity:
        params["simulateLiquidity"] = "true"

    provider_success = False
    provider_error = None
    provider_status_code = None
    data = _base_unknown()

    try:
        response = requests.get(
            HONEYPOT_API_URL,
            params=params,
            timeout=SELLABILITY_HTTP_TIMEOUT_SECONDS,
        )
        provider_status_code = getattr(response, "status_code", None)
        response.raise_for_status()
        data.update(_parse_payload(response.json()))
        provider_success = True
    except Exception as exc:
        provider_error = str(exc)

    data["local_evidence"] = local
    data.update({
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    })

    result = {
        "success": bool(provider_success),
        "provider_success": provider_success,
        "provider_status_code": provider_status_code,
        "local_evidence_complete": bool(local.get("completed")),
        "source": "sellability",
        "error": provider_error,
        "data": data,
    }

    if provider_success:
        try:
            _cache.set(
                "sellability",
                cache_key,
                json.dumps(result, default=str),
            )
        except Exception:
            pass

    return result


# SELLABILITY_PROVIDER_FALLBACK_V3


def _provider_verified(result):
    return bool(
        isinstance(result, dict)
        and result.get("provider_success") is True
        and result.get("success") is True
    )


def _provider_404(result):
    if not isinstance(result, dict):
        return False

    if result.get("provider_status_code") == 404:
        return True

    return "404" in str(result.get("error") or "")


def _fallback_metadata(
    result,
    *,
    mode,
    pair_error=None,
    token_error=None,
    pair_local_evidence=None,
):
    if not isinstance(result, dict):
        return result

    result = dict(result)
    data = dict(result.get("data") or {})
    data["provider_fallback_mode"] = mode

    if pair_error:
        data["provider_pair_error"] = str(pair_error)

    if token_error:
        data["provider_token_error"] = str(token_error)

    if isinstance(pair_local_evidence, dict):
        data["local_evidence"] = dict(pair_local_evidence)
        result["local_evidence_complete"] = bool(
            pair_local_evidence.get("completed")
        )

    result["data"] = data
    return result


def _normalized_flag(value):
    if value is True:
        return "1"
    if value is False:
        return "0"
    if value is None:
        return None

    normalized = str(value).strip().lower()

    if normalized in {"1", "true", "yes"}:
        return "1"
    if normalized in {"0", "false", "no"}:
        return "0"
    return None


def _goplus_tax_pct(value):
    if value in (None, ""):
        return None

    try:
        fraction = float(value)
    except (TypeError, ValueError):
        return None

    if fraction < 0:
        return None

    return fraction * 100.0


def _parse_goplus_payload(payload, token):
    result = payload.get("result") or {}
    token_data = result.get(token.lower()) or {}

    is_honeypot = _normalized_flag(token_data.get("is_honeypot"))
    cannot_buy = _normalized_flag(token_data.get("cannot_buy"))
    cannot_sell_all = _normalized_flag(
        token_data.get("cannot_sell_all")
    )
    is_in_dex = _normalized_flag(token_data.get("is_in_dex"))

    explicit_block = (
        is_honeypot == "1"
        or cannot_buy == "1"
        or cannot_sell_all == "1"
    )

    independently_sellable = (
        is_in_dex == "1"
        and cannot_buy == "0"
        and cannot_sell_all == "0"
        and is_honeypot != "1"
    )

    if explicit_block:
        sellable = False
    elif independently_sellable:
        sellable = True
    else:
        sellable = None

    return {
        "honeypot": (
            True
            if is_honeypot == "1"
            else False
            if is_honeypot == "0"
            else None
        ),
        "sellable": sellable,
        "sellability_checked": True,
        "sellability_provider": "goplus",
        "simulation_success": None,
        "simulation_error": None,
        "honeypot_reason": None,
        "provider_risk": None,
        "provider_risk_level": None,
        # GoPlus returns taxes as fractions; the canonical
        # mathematical cost model expects percentage points.
        "buy_tax": _goplus_tax_pct(token_data.get("buy_tax")),
        "sell_tax": _goplus_tax_pct(token_data.get("sell_tax")),
        "transfer_tax": None,
        "buy_gas": None,
        "sell_gas": None,
        "goplus_is_in_dex": is_in_dex,
        "goplus_is_honeypot": is_honeypot,
        "goplus_cannot_buy": cannot_buy,
        "goplus_cannot_sell_all": cannot_sell_all,
        "goplus_is_open_source": _normalized_flag(
            token_data.get("is_open_source")
        ),
        "goplus_api_code": payload.get("code"),
        "goplus_api_message": payload.get("message"),
    }


def _analyze_goplus_once(address):
    try:
        token = Web3.to_checksum_address(address)
    except Exception as exc:
        data = _base_unknown()
        data["sellability_provider"] = "goplus"
        return {
            "success": False,
            "provider_success": False,
            "provider_status_code": None,
            "source": "sellability",
            "error": str(exc),
            "data": data,
        }

    cache_key = f"goplus:bsc:{token.lower()}"

    try:
        cached = _cache.get(
            "sellability",
            cache_key,
            ttl_seconds=SELLABILITY_CACHE_TTL_SECONDS,
        )
    except Exception:
        cached = None

    if cached is not None:
        try:
            cached_result = json.loads(cached)
            if cached_result.get("provider_success") is True:
                return cached_result
        except Exception:
            pass

    provider_success = False
    provider_error = None
    provider_status_code = None
    data = _base_unknown()
    data["sellability_provider"] = "goplus"

    try:
        response = requests.get(
            f"{GOPLUS_TOKEN_SECURITY_URL}/{BSC_CHAIN_ID}",
            params={"contract_addresses": token},
            timeout=SELLABILITY_HTTP_TIMEOUT_SECONDS,
        )
        provider_status_code = getattr(response, "status_code", None)
        response.raise_for_status()
        payload = response.json()

        if str(payload.get("code")) != "1":
            raise ValueError(
                f"GoPlus API code={payload.get('code')}"
            )

        data.update(_parse_goplus_payload(payload, token))
        provider_success = True
    except Exception as exc:
        provider_error = str(exc)

    data.update({
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    })

    result = {
        "success": bool(provider_success),
        "provider_success": provider_success,
        "provider_status_code": provider_status_code,
        "source": "sellability",
        "error": provider_error,
        "data": data,
    }

    if provider_success:
        try:
            _cache.set(
                "sellability",
                cache_key,
                json.dumps(result, default=str),
            )
        except Exception:
            pass

    return result


def _with_goplus_fallback(address, primary):
    if not isinstance(primary, dict):
        return primary

    primary_data = dict(primary.get("data") or {})

    # Compatibility: a successful primary-provider response
    # must explicitly say that sellability was checked before
    # an UNKNOWN result can trigger the secondary provider.
    if (
        primary.get("provider_success") is True
        and primary_data.get("sellability_checked") is not True
    ):
        return primary

    # Never override an explicit Honeypot.is verdict.
    if primary_data.get("sellable") in {True, False}:
        return primary

    local = primary_data.get("local_evidence")

    # GoPlus is a second provider, not a replacement for
    # pair-local onchain evidence. Both must be available
    # before a new SELLABILITY_OK can be created.
    if not (
        isinstance(local, dict)
        and local.get("completed") is True
    ):
        return primary

    secondary = _analyze_goplus_once(address)

    if not _provider_verified(secondary):
        result = dict(primary)
        data = dict(primary_data)
        data["secondary_provider"] = "goplus"
        data["secondary_provider_attempted"] = True
        data["secondary_provider_success"] = False
        data["secondary_provider_error"] = str(
            secondary.get("error")
            if isinstance(secondary, dict)
            else "UNKNOWN"
        )
        result["data"] = data
        return result

    result = dict(secondary)
    data = dict(result.get("data") or {})
    data["local_evidence"] = dict(local)
    data["provider_fallback_mode"] = "GOPLUS"
    data["primary_sellability_provider"] = primary_data.get(
        "sellability_provider"
    )
    data["primary_provider_status_code"] = primary.get(
        "provider_status_code"
    )
    data["primary_simulation_error"] = primary_data.get(
        "simulation_error"
    )
    data["secondary_provider"] = "goplus"
    data["secondary_provider_attempted"] = True
    data["secondary_provider_success"] = True
    result["local_evidence_complete"] = True
    result["data"] = data
    return result


def analyze(address, *, pair=None):
    """
    Provider-backed sellability chain.

    Honeypot.is remains primary:
      pair
        -> HTTP 404 only: token-only
        -> HTTP 404 only: simulateLiquidity=true

    If the primary result is still UNKNOWN and pair-local
    onchain evidence is complete, GoPlus is queried as an
    independent second provider.

    An explicit Honeypot.is sellable/honeypot verdict is
    never overridden. Local evidence alone cannot create
    SELLABILITY_OK.
    """

    first = _analyze_provider_once(address, pair=pair)
    pair_local_evidence = None

    if isinstance(first, dict):
        first_data = first.get("data") or {}
        if isinstance(first_data, dict):
            candidate_local = first_data.get("local_evidence")
            if isinstance(candidate_local, dict):
                pair_local_evidence = candidate_local

    if _provider_verified(first):
        return _with_goplus_fallback(address, first)

    if not pair or not _provider_404(first):
        return _with_goplus_fallback(address, first)

    pair_error = first.get("error") if isinstance(first, dict) else None

    token_only = _analyze_provider_once(address, pair=None)

    if _provider_verified(token_only):
        primary = _fallback_metadata(
            token_only,
            mode="TOKEN_ONLY",
            pair_error=pair_error,
            pair_local_evidence=pair_local_evidence,
        )
        return _with_goplus_fallback(address, primary)

    if not _provider_404(token_only):
        primary = _fallback_metadata(
            token_only,
            mode="TOKEN_ONLY_FAILED",
            pair_error=pair_error,
            pair_local_evidence=pair_local_evidence,
        )
        return _with_goplus_fallback(address, primary)

    token_error = (
        token_only.get("error")
        if isinstance(token_only, dict)
        else None
    )

    simulated = _analyze_provider_once(
        address,
        pair=None,
        simulate_liquidity=True,
    )

    primary = _fallback_metadata(
        simulated,
        mode="SIMULATE_LIQUIDITY",
        pair_error=pair_error,
        token_error=token_error,
        pair_local_evidence=pair_local_evidence,
    )

    return _with_goplus_fallback(address, primary)
