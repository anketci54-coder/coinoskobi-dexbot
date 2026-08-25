import json
import math

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

    if not math.isfinite(fraction) or fraction < 0:
        return None

    return fraction * 100.0


def _fraction(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    if number < 0 or number > 1:
        return None

    return number


def _positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number) or number <= 0:
        return None

    return number


def _goplus_primary_pair(token_data, pair):
    pair_key = str(pair or "").strip().lower()
    if not pair_key:
        return False, False

    raw_dex = token_data.get("dexs")
    if not isinstance(raw_dex, list):
        raw_dex = token_data.get("dex")
    if not isinstance(raw_dex, list):
        raw_dex = []

    rows = []
    pair_in_dex = False

    for item in raw_dex:
        if not isinstance(item, dict):
            continue

        item_pair = str(item.get("pair") or "").strip().lower()
        liquidity = _positive_number(item.get("liquidity"))

        if item_pair == pair_key:
            pair_in_dex = True

        if item_pair and liquidity is not None:
            rows.append((item_pair, liquidity))

    if not rows:
        return pair_in_dex, False

    max_liquidity = max(value for _, value in rows)
    leaders = [
        item_pair
        for item_pair, value in rows
        if value == max_liquidity
    ]

    # GoPlus lp_holders describes the dominant/main LP.
    # Bind that evidence only when the target pair is the
    # unique highest-liquidity DEX pair. Ties stay UNKNOWN.
    is_primary = (
        len(leaders) == 1
        and leaders[0] == pair_key
    )

    return pair_in_dex, is_primary


def _goplus_locked_fraction(token_data, *, pair_is_primary):
    if not pair_is_primary:
        return None, 0

    holders = token_data.get("lp_holders")
    if not isinstance(holders, list):
        return None, 0

    locked = 0.0
    count = 0

    for holder in holders:
        if not isinstance(holder, dict):
            continue

        if _normalized_flag(holder.get("is_locked")) != "1":
            continue

        fraction = _fraction(holder.get("percent"))
        if fraction is None:
            continue

        locked += fraction
        count += 1

    if count <= 0 or locked <= 0:
        return None, 0

    return min(1.0, locked), count


def _parse_goplus_payload(payload, token, *, pair=None):
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

    pair_in_dex, pair_is_primary = _goplus_primary_pair(
        token_data,
        pair,
    )
    locked_fraction, locked_count = _goplus_locked_fraction(
        token_data,
        pair_is_primary=pair_is_primary,
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
        "goplus_pair_in_dex": pair_in_dex,
        "goplus_pair_is_primary_lp": pair_is_primary,
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
    cache_key = f"goplus:bsc:{token.lower()}:{pair_key or 'token'}"

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


def _local_lp_protected_fraction(local):
    if not isinstance(local, dict):
        return None

    lp = local.get("lp_security")
    if not isinstance(lp, dict):
        return None

    return _fraction(lp.get("lp_protected_fraction"))


def _merge_goplus_lp_evidence(primary, secondary, *, pair=None):
    result = dict(primary)
    data = dict(result.get("data") or {})
    local = data.get("local_evidence")

    if not isinstance(local, dict):
        return result

    local = dict(local)
    lp = local.get("lp_security")

    if not isinstance(lp, dict):
        return result

    lp = dict(lp)
    secondary_data = (
        secondary.get("data")
        if isinstance(secondary, dict)
        else None
    )

    data["secondary_provider"] = "goplus"
    data["secondary_provider_attempted"] = True
    data["secondary_provider_success"] = bool(
        _provider_verified(secondary)
    )
    data["goplus_lp_protection_verified"] = False

    if not isinstance(secondary_data, dict):
        local["lp_security"] = lp
        data["local_evidence"] = local
        result["data"] = data
        return result

    fraction = _fraction(
        secondary_data.get(
            "goplus_lp_locked_fraction_reported"
        )
    )
    pair_is_primary = (
        secondary_data.get("goplus_pair_is_primary_lp")
        is True
    )
    pair_in_dex = (
        secondary_data.get("goplus_pair_in_dex")
        is True
    )

    if (
        _provider_verified(secondary)
        and pair_in_dex
        and pair_is_primary
        and fraction is not None
        and fraction > 0
    ):
        onchain_fraction = _fraction(
            lp.get("lp_protected_fraction")
        )
        onchain_fraction = onchain_fraction or 0.0
        protected = max(onchain_fraction, fraction)

        lp["onchain_state"] = lp.get("state")
        lp["onchain_lp_protected_fraction"] = onchain_fraction
        lp["lp_protected_fraction"] = protected
        lp["lp_withdrawable_fraction"] = max(
            0.0,
            1.0 - protected,
        )
        lp["protection_evidence_present"] = True
        lp["state"] = "PROTECTION_EVIDENCE_PRESENT"
        lp["lp_protection_source"] = (
            "GOPLUS_PRIMARY_POOL_LOCKED_HOLDERS"
        )
        lp["goplus_pair"] = str(pair or "")
        lp["goplus_locked_fraction"] = fraction
        lp["goplus_locked_holder_count"] = (
            secondary_data.get(
                "goplus_lp_locked_holder_count"
            )
        )
        data["lp_evidence_fallback_mode"] = "GOPLUS"
        data["goplus_lp_protection_verified"] = True

    local["lp_security"] = lp
    data["local_evidence"] = local
    result["local_evidence_complete"] = bool(
        local.get("completed")
    )
    result["data"] = data
    return result


def _with_goplus_fallback(address, primary, *, pair=None):
    if not isinstance(primary, dict):
        return primary

    primary_data = dict(primary.get("data") or {})

    # Compatibility: a successful primary-provider response
    # must explicitly say sellability was checked before its
    # UNKNOWN result can authorize a secondary sellability verdict.
    if (
        primary.get("provider_success") is True
        and primary_data.get("sellability_checked") is not True
    ):
        return primary

    # Never override an explicit negative Honeypot.is verdict.
    if primary_data.get("sellable") is False:
        return primary

    local = primary_data.get("local_evidence")

    if not (
        isinstance(local, dict)
        and local.get("completed") is True
    ):
        return primary

    current_lp_fraction = _local_lp_protected_fraction(local)
    needs_lp_evidence = (
        current_lp_fraction is None
        or current_lp_fraction <= 0
    )
    needs_sellability = (
        primary_data.get("sellable") is None
    )

    if not needs_lp_evidence and not needs_sellability:
        return primary

    secondary = _analyze_goplus_once(
        address,
        pair=pair,
    )

    result = _merge_goplus_lp_evidence(
        primary,
        secondary,
        pair=pair,
    )
    data = dict(result.get("data") or {})

    if not _provider_verified(secondary):
        data["secondary_provider_error"] = str(
            secondary.get("error")
            if isinstance(secondary, dict)
            else "UNKNOWN"
        )
        result["data"] = data
        return result

    secondary_data = dict(secondary.get("data") or {})

    # A positive/negative secondary sellability verdict is used
    # only when the primary provider remained UNKNOWN. Existing
    # Honeypot.is SELLABILITY_OK remains the canonical sellability
    # verdict while GoPlus can independently enrich LP evidence.
    if needs_sellability and secondary_data.get("sellable") in {
        True,
        False,
    }:
        enriched_local = data.get("local_evidence")
        merged = dict(secondary)
        merged_data = dict(secondary_data)
        merged_data["local_evidence"] = enriched_local
        merged_data["provider_fallback_mode"] = "GOPLUS"
        merged_data["primary_sellability_provider"] = (
            primary_data.get("sellability_provider")
        )
        merged_data["primary_provider_status_code"] = (
            primary.get("provider_status_code")
        )
        merged_data["primary_simulation_error"] = (
            primary_data.get("simulation_error")
        )
        merged_data["secondary_provider"] = "goplus"
        merged_data["secondary_provider_attempted"] = True
        merged_data["secondary_provider_success"] = True

        for key in (
            "lp_evidence_fallback_mode",
            "goplus_lp_protection_verified",
        ):
            if key in data:
                merged_data[key] = data[key]

        merged["local_evidence_complete"] = bool(
            isinstance(enriched_local, dict)
            and enriched_local.get("completed") is True
        )
        merged["data"] = merged_data
        return merged

    data["secondary_provider"] = "goplus"
    data["secondary_provider_attempted"] = True
    data["secondary_provider_success"] = True
    result["data"] = data
    return result


def analyze(address, *, pair=None):
    """
    Provider-backed sellability and LP-evidence chain.

    Honeypot.is remains the primary sellability provider:
      pair
        -> HTTP 404 only: token-only
        -> HTTP 404 only: simulateLiquidity=true

    GoPlus has two narrow fallback roles:
      1. If primary sellability remains UNKNOWN, it may provide an
         independent sellability verdict.
      2. If pair-local LP protection is unproven, its locked LP
         holder data may enrich persistent-liquidity evidence only
         when the target pair is the unique highest-liquidity DEX
         pair reported for that token.

    Explicit negative Honeypot.is verdicts are never overridden.
    Missing/ambiguous GoPlus LP data remains UNKNOWN.
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
