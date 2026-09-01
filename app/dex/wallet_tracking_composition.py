from app.dex.successful_wallet import SuccessfulWalletTracker
from app.dex.wallet_holdings import WalletHoldingsReadModel
from app.dex.related_wallet_evidence import related_wallet_evidence


class WalletTrackingComposition:
    """Phase 9 composition for selected observed wallets.

    Keeps successful-outcome, holdings, and related-wallet evidence behind
    one bounded observation-only boundary. Callers must supply chain-derived
    evidence; this component never guesses identity or grants trade authority.
    """

    def __init__(self, *, successful=None, holdings=None):
        self.successful = successful or SuccessfulWalletTracker()
        self.holdings = holdings or WalletHoldingsReadModel()

    def observe_outcome(self, wallet_id, token_id, return_pct, *, realized=False):
        return self.successful.observe_outcome(
            wallet_id, token_id, return_pct, realized=realized
        )

    def observe_holding(self, wallet_id, token_id, balance, *, value_usd=None, observed_at=None):
        return self.holdings.observe(
            wallet_id,
            token_id,
            balance,
            value_usd=value_usd,
            observed_at=observed_at,
        )

    def related_wallet(self, wallet_a, wallet_b, **evidence):
        return related_wallet_evidence(wallet_a, wallet_b, **evidence)

    def snapshot(self, wallet_id):
        return {
            "state": "READY",
            "wallet_id": str(wallet_id or "").strip().lower() or None,
            "performance": self.successful.snapshot(wallet_id),
            "holdings": self.holdings.snapshot(wallet_id),
            "identity_guessing": False,
            "entity_auto_merge": False,
            "trade_signal": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }
