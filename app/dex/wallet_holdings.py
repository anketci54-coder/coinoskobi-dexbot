from collections import OrderedDict
import math


class WalletHoldingsReadModel:
    """Bounded observed holdings for selected Phase 9 wallets.

    This is an observation readmodel, not a portfolio authority. Values must
    come from explicit chain/provider evidence supplied by the caller.
    """

    def __init__(self, max_wallets=512, max_tokens_per_wallet=128):
        self.max_wallets = max(1, int(max_wallets))
        self.max_tokens_per_wallet = max(1, int(max_tokens_per_wallet))
        self._wallets = OrderedDict()

    def observe(self, wallet_id, token_id, balance, *, value_usd=None, observed_at=None):
        wallet_id = _id(wallet_id)
        token_id = _id(token_id)
        balance = _nonnegative(balance)
        value_usd = _nonnegative(value_usd, allow_none=True)

        if not wallet_id or not token_id or balance is None:
            return _out("INVALID")

        if wallet_id not in self._wallets and len(self._wallets) >= self.max_wallets:
            self._wallets.popitem(last=False)

        holdings = self._wallets.setdefault(wallet_id, OrderedDict())
        self._wallets.move_to_end(wallet_id)

        if balance == 0:
            holdings.pop(token_id, None)
        else:
            holdings[token_id] = {
                "token_id": token_id,
                "balance": balance,
                "value_usd": value_usd,
                "observed_at": observed_at,
            }
            holdings.move_to_end(token_id)

        while len(holdings) > self.max_tokens_per_wallet:
            holdings.popitem(last=False)

        return self.snapshot(wallet_id)

    def snapshot(self, wallet_id):
        wallet_id = _id(wallet_id)
        if not wallet_id or wallet_id not in self._wallets:
            return _out("UNKNOWN", wallet_id=wallet_id)

        holdings = list(self._wallets[wallet_id].values())
        known_value = sum(
            row["value_usd"] for row in holdings if row["value_usd"] is not None
        )
        return _out(
            "READY",
            wallet_id=wallet_id,
            holdings=holdings,
            token_count=len(holdings),
            known_value_usd=known_value,
            bounded=True,
        )


def _id(value):
    value = str(value or "").strip().lower()
    return value or None


def _nonnegative(value, allow_none=False):
    if value is None and allow_none:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _out(state, **payload):
    return {
        "state": state,
        **payload,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
