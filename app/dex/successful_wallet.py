from collections import OrderedDict
import math


class SuccessfulWalletTracker:
    """Bounded Phase 9 outcome memory for observed wallets.

    Evidence only. It never grants decision, paper, wallet, signing,
    or execution authority.
    """

    def __init__(self, max_wallets=1024, max_outcomes_per_wallet=64):
        self.max_wallets = max(1, int(max_wallets))
        self.max_outcomes_per_wallet = max(1, int(max_outcomes_per_wallet))
        self._wallets = OrderedDict()

    def observe_outcome(self, wallet_id, token_id, return_pct, *, realized=False):
        wallet_id = str(wallet_id or "").strip().lower()
        token_id = str(token_id or "").strip().lower()
        value = _finite(return_pct)

        if not wallet_id or not token_id or value is None:
            return _out("INVALID")

        if wallet_id not in self._wallets and len(self._wallets) >= self.max_wallets:
            self._wallets.popitem(last=False)

        row = self._wallets.setdefault(wallet_id, OrderedDict())
        self._wallets.move_to_end(wallet_id)
        row[token_id] = {"return_pct": value, "realized": bool(realized)}
        row.move_to_end(token_id)

        while len(row) > self.max_outcomes_per_wallet:
            row.popitem(last=False)

        return self.snapshot(wallet_id)

    def snapshot(self, wallet_id):
        wallet_id = str(wallet_id or "").strip().lower()
        rows = self._wallets.get(wallet_id)
        if not rows:
            return _out("UNKNOWN", wallet_id=wallet_id or None)

        values = [r["return_pct"] for r in rows.values()]
        realized = [r["return_pct"] for r in rows.values() if r["realized"]]
        wins = sum(v > 0 for v in values)
        losses = sum(v < 0 for v in values)
        sample = len(values)
        win_rate = wins / sample if sample else 0.0
        avg_return = sum(values) / sample if sample else None

        # Reputation requires repetition; one moonshot cannot qualify a wallet.
        if len(realized) >= 20 and win_rate >= 0.60 and (avg_return or 0) > 0:
            state = "SUCCESSFUL"
        elif sample >= 5:
            state = "OBSERVED"
        else:
            state = "INSUFFICIENT_SAMPLE"

        return _out(
            state,
            wallet_id=wallet_id,
            sample_size=sample,
            realized_sample_size=len(realized),
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            average_return_pct=avg_return,
            bounded=True,
        )


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


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
