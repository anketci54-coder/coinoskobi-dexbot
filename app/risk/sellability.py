import json
from decimal import Decimal, InvalidOperation

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


# SELLABILITY_PROVIDER_FALLBACK_V4


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


def _fraction(value):
    if value in (None, ""):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number < 0 or number > 1:
        return None

    return number


def _goplus_lp_total_supply_raw(value):
    if value in (None, ""):
        return None

    try:
        supply = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None

    if supply <= 0:
        return None

    raw = supply * Decimal(10**18)

    if raw != raw.to_integral_value():
        return None

    return int(raw)


def _goplus_pair_in_dex(token_data, pair):
    if not pair:
        return None

    wanted = str(pair).strip().lower()

    for item in token_data.get("dex") or []:
        if not isinstance(item, dict):
            continue

        candidate = str(
            item.get("pair")
            or item.get("pair_address")
            or ""
        ).strip().lower()

        if candidate and candidate == wanted:
            return True

    return False


def _goplus_locked_lp_fraction(token_data):
    total = 0.0
    count = 0

    for holder in token_data.get("lp_holders") or []:
        if not isinstance(holder, dict):
            continue

        if _normalized_flag(holder.get("is_locked")) != "1":
            continue

        fraction = _fraction(holder.get("percent"))

        if fraction is None or fraction <= 0:
            continue

        total += fraction
        count += 1

    return min(1.0, total), count


def _parse_goplus_payload(payload, token, pair=None):
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

    locked_fraction, locked_count = (
        _goplus_locked_lp_fraction(token_data)
    )

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
        "goplus_pair_in_dex": _goplus_pair_in_dex(
            token_data,
            pair,
        ),
        "goplus_lp_total_supply_raw": (
            _goplus_lp_total_supply_raw(
                token_data.get("lp_total_supply")
            )
        ),
        "goplus_lp_locked_fraction_reported": locked_fraction,
        "goplus_lp_locked_holder_count": locked_count,
        "goplus_api_code": payload.get("code"),
        "goplus_api_message": payload.get("message"),
    }


def _analyze_goplus_once(address, *, pair=None):
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

    pair_key = str(pair or "").strip().lower()
    cache_key = f"goplus:bsc:{token.lower()}:{pair_key}"

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

        data.update(
            _parse_goplus_payload(
                payload,
                token,
                pair=pair,
            )
        )
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


def _local_lp_needs_secondary(local):
    if not isinstance(local, dict):
        return False

    lp = local.get("lp_security")

    if not isinstance(lp, dict):
        return False

    try:
        protected = float(lp.get("lp_protected_fraction"))
    except (TypeError, ValueError):
        protected = None

    return protected is not None and protected <= 0


def _enrich_local_lp_from_goplus(local, secondary_data, pair):
    local = dict(local or {})
    lp = dict(local.get("lp_security") or {})

    try:
        onchain_total = int(lp.get("total_supply_raw"))
    except (TypeError, ValueError):
        onchain_total = None

    provider_total = secondary_data.get(
        "goplus_lp_total_supply_raw"
    )
    provider_fraction = secondary_data.get(
        "goplus_lp_locked_fraction_reported"
    )
    pair_matches = secondary_data.get("goplus_pair_in_dex") is True

    verified = bool(
        pair_matches
        and onchain_total is not None
        and onchain_total > 0
        and provider_total == onchain_total
        and provider_fraction is not None
        and provider_fraction > 0
        and provider_fraction <= 1
    )

    if not verified:
        return local, False

    onchain_state = lp.get("state")
    onchain_fraction = lp.get("lp_protected_fraction")

    lp.update({
        "onchain_state": onchain_state,
        "onchain_lp_protected_fraction": onchain_fraction,
        "state": "PROTECTION_EVIDENCE_PRESENT",
        "protection_evidence_present": True,
        "lp_protected_fraction": provider_fraction,
        "lp_withdrawable_fraction": 1.0 - provider_fraction,
        "lp_protection_source": "GOPLUS_LOCKED_LP_HOLDERS",
        "goplus_pair": str(pair or ""),
        "goplus_lp_total_supply_raw": provider_total,
        "goplus_lp_locked_holder_count": secondary_data.get(
            "goplus_lp_locked_holder_count"
        ),
        "economic_safety_authority": False,
        "trade_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    })

    local["lp_security"] = lp
    return local, True


def _with_goplus_fallback(address, primary, *, pair=None):
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

    local = primary_data.get("local_evidence")
    local_complete = bool(
        isinstance(local, dict)
        and local.get("completed") is True
    )

    # An explicit negative Honeypot.is verdict remains final.
    # No secondary provider can weaken it.
    if primary_data.get("sellable") is False:
        return primary

    needs_sellability = primary_data.get("sellable") is None
    needs_lp = bool(
        pair
        and local_complete
        and _local_lp_needs_secondary(local)
    )

    if not needs_sellability and not needs_lp:
        return primary

    # GoPlus is a second provider, not a replacement for
    # pair-local onchain evidence. Both must be available
    # before it can create SELLABILITY_OK or LP protection.
    if not local_complete:
        return primary

    secondary = _analyze_goplus_once(
        address,
        pair=pair,
    )

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

    secondary_data = dict(secondary.get("data") or {})
    enriched_local, lp_verified = (
        _enrich_local_lp_from_goplus(
            local,
            secondary_data,
            pair,
        )
    )

    if needs_sellability:
        result = dict(secondary)
        data = dict(secondary_data)
        data["provider_fallback_mode"] = "GOPLUS"
    else:
        # Honeypot.is already confirmed sellability. Preserve
        # that primary verdict and use GoPlus only as an
        # independently verified LP-lock evidence source.
        result = dict(primary)
        data = dict(primary_data)

    data["local_evidence"] = enriched_local
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
    data["goplus_lp_protection_verified"] = lp_verified

    if lp_verified:
        data["lp_evidence_fallback_mode"] = "GOPLUS"

    result["local_evidence_complete"] = True
    result["data"] = data
    return result


def analyze(address, *, pair=None):
    """
    Provider-backed sellability and LP-evidence chain.

    Honeypot.is remains primary:
      pair
        -> HTTP 404 only: token-only
        -> HTTP 404 only: simulateLiquidity=true

    GoPlus is independent secondary evidence when:
    - primary sellability remains UNKNOWN, or
    - local pair LP exists but burn/known-locker protection
      is still unproven.

    A GoPlus LP lock is accepted only when the requested pair
    is present in GoPlus DEX evidence and GoPlus LP total supply
    exactly matches the onchain pair totalSupply. An explicit
    negative Honeypot.is verdict is never overridden.
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
        return _with_goplus_fallback(
            address,
            first,
            pair=pair,
        )

    if not pair or not _provider_404(first):
        return _with_goplus_fallback(
            address,
            first,
            pair=pair,
        )

    pair_error = first.get("error") if isinstance(first, dict) else None

    token_only = _analyze_provider_once(address, pair=None)

    if _provider_verified(token_only):
        primary = _fallback_metadata(
            token_only,
            mode="TOKEN_ONLY",
            pair_error=pair_error,
            pair_local_evidence=pair_local_evidence,
        )
        return _with_goplus_fallback(
            address,
            primary,
            pair=pair,
        )

    if not _provider_404(token_only):
        primary = _fallback_metadata(
            token_only,
            mode="TOKEN_ONLY_FAILED",
            pair_error=pair_error,
            pair_local_evidence=pair_local_evidence,
        )
        return _with_goplus_fallback(
            address,
            primary,
            pair=pair,
        )

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

    return _with_goplus_fallback(
        address,
        primary,
        pair=pair,
    )
