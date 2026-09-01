from app.dex.wallet_tracking_composition import WalletTrackingComposition


class RuntimeWalletTracking:
    """Safe adapter from proven native actor identity to Phase 9 tracking.

    The actor wallet_id must already come from RuntimeActorIntelligence's
    transaction.from resolution. This adapter does not resolve or infer identity.
    """

    def __init__(self, tracking=None):
        self.tracking = tracking or WalletTrackingComposition()

    def actor_snapshot(self, actor_result):
        actor = dict(actor_result or {})
        wallet_id = str(actor.get("wallet_id") or "").strip().lower()
        origin = actor.get("transaction_origin") or {}

        if (
            actor.get("state") != "OBSERVED"
            or not wallet_id
            or origin.get("state") != "READY"
        ):
            return _out("UNKNOWN", wallet_id=wallet_id or None)

        return {
            **self.tracking.snapshot(wallet_id),
            "identity_source": "TRANSACTION_FROM_ONLY",
            "identity_guessing": False,
        }

    def observe_outcome(self, actor_result, token_id, return_pct, *, realized=False):
        snapshot = self.actor_snapshot(actor_result)
        if snapshot.get("state") != "READY":
            return _out("UNKNOWN")
        return self.tracking.observe_outcome(
            snapshot["wallet_id"], token_id, return_pct, realized=realized
        )

    def observe_holding(self, actor_result, token_id, balance, *, value_usd=None, observed_at=None):
        snapshot = self.actor_snapshot(actor_result)
        if snapshot.get("state") != "READY":
            return _out("UNKNOWN")
        return self.tracking.observe_holding(
            snapshot["wallet_id"],
            token_id,
            balance,
            value_usd=value_usd,
            observed_at=observed_at,
        )


def _out(state, **payload):
    return {
        "state": state,
        **payload,
        "identity_guessing": False,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
