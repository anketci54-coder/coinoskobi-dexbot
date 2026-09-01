from app.dex.runtime_actor_intelligence import RuntimeActorIntelligence
from app.dex.runtime_wallet_tracking import RuntimeWalletTracking


class RuntimeActorTrackingComposition:
    """Canonical Phase 9 composition boundary for actor + wallet tracking.

    Existing RuntimeActorIntelligence remains the sole identity producer.
    Successful-wallet tracking only consumes its transaction.from proof.
    """

    def __init__(self, *, actor=None, tracking=None):
        self.actor = actor or RuntimeActorIntelligence()
        self.tracking = tracking or RuntimeWalletTracking()

    async def observe_event(self, event, *, direction="UNKNOWN"):
        actor = await self.actor.observe_event(event, direction=direction)
        return {
            "actor": actor,
            "wallet_tracking": self.tracking.actor_snapshot(actor),
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }

    async def observe_retraction(self, event):
        result = await self.actor.observe_retraction(event)
        return {
            "actor": result,
            "wallet_tracking_mutated": False,
            "reason": "OUTCOME_AND_HOLDINGS_REQUIRE_EXPLICIT_EVIDENCE",
            "decision_authority": False,
            "execution_authority": False,
        }

    def snapshot(self, pair):
        actor = self.actor.snapshot(pair)
        wallet_id = actor.get("wallet_id")
        return {
            "actor": actor,
            "wallet_tracking": (
                self.tracking.tracking.snapshot(wallet_id)
                if actor.get("state") == "READY" and wallet_id
                else {"state": "UNKNOWN"}
            ),
            "decision_authority": False,
            "execution_authority": False,
        }
