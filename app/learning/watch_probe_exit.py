import math
import threading
import time

from web3 import Web3

from app.chains.bsc import w3
from app.config.contracts import PANCAKE_ROUTER, WBNB
from app.risk.exit_feasibility import (
    PAIR_ABI,
    ERC20_ABI,
    ROUTER_ABI,
    _wbnb_usd,
)
from app.risk.sellability import analyze as sellability_analyze


MAX_PROBES_PER_MINUTE = 4
RETRY_SECONDS = 900.0

_BUDGET_LOCK = threading.Lock()
_BUDGET_WINDOW = None
_BUDGET_USED = 0


def _positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number) or number <= 0:
        return None

    return number


def _acquire_budget(now):
    global _BUDGET_WINDOW
    global _BUDGET_USED

    window = int(float(now) // 60)

    with _BUDGET_LOCK:
        if _BUDGET_WINDOW != window:
            _BUDGET_WINDOW = window
            _BUDGET_USED = 0

        if _BUDGET_USED >= MAX_PROBES_PER_MINUTE:
            return False

        _BUDGET_USED += 1
        return True


def _result(
    state,
    *,
    attempted,
    quality=None,
    reason=None,
    exit_usdt=None,
):
    return {
        "state": state,
        "attempted": bool(attempted),
        "quality": quality,
        "reason": reason,
        "realizable_exit_usdt": exit_usdt,
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }


def _exact_router_exit_usdt(token, pair, token_amount):
    token_amount = _positive(token_amount)
    if token_amount is None:
        return None

    token_address = Web3.to_checksum_address(token)
    pair_address = Web3.to_checksum_address(pair)
    wbnb = Web3.to_checksum_address(WBNB)

    pair_contract = w3.eth.contract(
        address=pair_address,
        abi=PAIR_ABI,
    )

    token0 = Web3.to_checksum_address(
        pair_contract.functions.token0().call()
    )
    token1 = Web3.to_checksum_address(
        pair_contract.functions.token1().call()
    )

    if {
        token0.lower(),
        token1.lower(),
    } != {
        token_address.lower(),
        wbnb.lower(),
    }:
        return None

    token_contract = w3.eth.contract(
        address=token_address,
        abi=ERC20_ABI,
    )

    decimals = int(
        token_contract.functions.decimals().call()
    )

    raw_amount = int(
        token_amount * (10 ** decimals)
    )
    if raw_amount <= 0:
        return None

    router = w3.eth.contract(
        address=Web3.to_checksum_address(PANCAKE_ROUTER),
        abi=ROUTER_ABI,
    )

    amounts = (
        router.functions
        .getAmountsOut(
            raw_amount,
            [token_address, wbnb],
        )
        .call()
    )

    if not amounts or int(amounts[-1]) <= 0:
        return None

    wbnb_out = int(amounts[-1]) / 1e18
    wbnb_usd, _ = _wbnb_usd(router)

    if wbnb_usd is None or wbnb_usd <= 0:
        return None

    return wbnb_out * float(wbnb_usd)


def probe_watch_exit(
    *,
    token,
    pool,
    token_amount,
    now=None,
):
    now = time.time() if now is None else float(now)

    if not _acquire_budget(now):
        return _result(
            "DEFERRED",
            attempted=False,
            quality="BOUNDED",
            reason="EXIT_PROBE_BUDGET_EXHAUSTED",
        )

    try:
        sellability = sellability_analyze(
            token,
            pair=pool,
        )
    except Exception:
        return _result(
            "UNVERIFIED",
            attempted=True,
            quality="PROVIDER_ERROR",
            reason="SELLABILITY_PROBE_FAILED",
        )

    data = (
        sellability.get("data") or {}
        if isinstance(sellability, dict)
        else {}
    )

    if (
        not isinstance(sellability, dict)
        or sellability.get("success") is not True
        or data.get("sellable") is not True
    ):
        return _result(
            "UNVERIFIED",
            attempted=True,
            quality="SELLABILITY_UNVERIFIED",
            reason="SELLABILITY_NOT_VERIFIED",
        )

    try:
        exit_usdt = _exact_router_exit_usdt(
            token,
            pool,
            token_amount,
        )
    except Exception:
        exit_usdt = None

    exit_usdt = _positive(exit_usdt)

    if exit_usdt is None:
        return _result(
            "LIMITED",
            attempted=True,
            quality="SELLABILITY_ONLY",
            reason="EXACT_ROUTE_QUOTE_UNAVAILABLE",
        )

    return _result(
        "VERIFIED",
        attempted=True,
        quality="SELLABILITY_PLUS_EXACT_ROUTE_QUOTE",
        reason="SIMULATED_EXIT_VERIFIED",
        exit_usdt=exit_usdt,
    )
