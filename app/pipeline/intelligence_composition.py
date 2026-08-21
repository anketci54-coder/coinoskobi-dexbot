from app.dex.market_quality import analyze_market_quality
from app.dex.flow_spread import flow_spread
from app.dex.flow_confirmation import confirm_flow
from app.dex.flow_divergence import evaluate_divergence
from app.dex.flow_quality import evaluate_flow_quality
from app.dex.market_regime import classify_market_regime

from app.dex.wallet_readmodel import WalletReadModel
from app.dex.adversary_readmodel import AdversaryReadModel
from app.dex.adversary_market_bridge import (
    bind_adversary_market_context,
)
from app.dex.native_event_binding import (
    bind_native_event_context,
)


class RuntimeIntelligenceComposition:
    def __init__(
        self,
        wallet_max_entries=4096,
        adversary_max_entries=4096,
    ):
        self.wallet_readmodel = WalletReadModel(
            wallet_max_entries
        )

        self.adversary_readmodel = AdversaryReadModel(
            adversary_max_entries
        )

    def update_wallet(
        self,
        wallet_id,
        payload,
    ):
        return self.wallet_readmodel.put(
            wallet_id,
            payload,
        )

    def update_adversary(
        self,
        actor_key,
        payload,
    ):
        return self.adversary_readmodel.put(
            actor_key,
            payload,
        )

    def bind_native_event(
        self,
        normalized_event,
        integrity,
        buffer_health,
        subscription_health,
    ):
        return bind_native_event_context(
            normalized_event,
            integrity,
            buffer_health,
            subscription_health,
        )

    def build(
        self,
        token_address,
        *,
        market_input=None,
        flow_input=None,
        wallet_id=None,
        adversary_key=None,
    ):
        market_input = dict(
            market_input or {}
        )

        flow_input = dict(
            flow_input or {}
        )

        market_quality = (
            analyze_market_quality(
                volume_usd=market_input.get(
                    "volume_usd"
                ),
                buy_volume_usd=market_input.get(
                    "buy_volume_usd"
                ),
                sell_volume_usd=market_input.get(
                    "sell_volume_usd"
                ),
                buyers=market_input.get(
                    "buyers"
                ),
                sellers=market_input.get(
                    "sellers"
                ),
                buys=market_input.get(
                    "buys"
                ),
                sells=market_input.get(
                    "sells"
                ),
                liquidity_usd=market_input.get(
                    "liquidity_usd"
                ),
                previous_liquidity_usd=(
                    market_input.get(
                        "previous_liquidity_usd"
                    )
                ),
            )
        )

        spread = flow_spread(
            flow_input.get(
                "buy_flow"
            ),
            flow_input.get(
                "sell_flow"
            ),
            prev_spread=flow_input.get(
                "prev_spread"
            ),
            prev_velocity=flow_input.get(
                "prev_velocity"
            ),
            freshness=flow_input.get(
                "freshness",
                "UNKNOWN",
            ),
            coverage=flow_input.get(
                "coverage"
            ),
        )

        direction = (
            flow_input.get(
                "direction"
            )
            or "UNKNOWN"
        )

        confirmation = confirm_flow(
            direction,
            spread.get("spread"),
            spread.get("velocity"),
            market_quality.get(
                "participation_state"
            ),
        )

        divergence = evaluate_divergence(
            flow_input.get(
                "price_direction",
                "UNKNOWN",
            ),
            spread.get("spread"),
            spread.get("velocity"),
        )

        quality = evaluate_flow_quality(
            flow_input.get(
                "unique_wallets"
            ),
            flow_input.get(
                "tx_count"
            ),
            flow_input.get(
                "largest_actor_share"
            ),
        )

        regime = classify_market_regime(
            direction,
            confirmation.get(
                "confirmation",
                "UNKNOWN",
            ),
            divergence.get(
                "divergence_state",
                "UNKNOWN",
            ),
            quality.get(
                "flow_quality",
                "UNKNOWN",
            ),
        )

        wallet_read = (
            self.wallet_readmodel.get(
                wallet_id
            )
            if wallet_id
            else {
                "state": "UNKNOWN",
                "payload": None,
            }
        )

        adversary_read = (
            self.adversary_readmodel.get(
                adversary_key
            )
            if adversary_key
            else {
                "state": "UNKNOWN",
                "payload": None,
            }
        )

        wallet_payload = (
            wallet_read.get(
                "payload"
            )
            or {}
        )

        adversary_payload = (
            adversary_read.get(
                "payload"
            )
            or {}
        )

        adversary_bridge = (
            bind_adversary_market_context(
                wallet_payload,
                adversary_payload,
            )
        )

        runtime_connected = {
            "phase5_market": True,
            "phase7_flow_regime": True,
            "phase8_native_binding": True,
            "phase9_wallet_readmodel": True,
            "phase10_adversary_readmodel": True,
            "phase10_adversary_bridge": True,
        }

        return {
            "token": token_address,
            "market_quality": market_quality,
            "flow_spread": spread,
            "flow_confirmation": confirmation,
            "flow_divergence": divergence,
            "flow_quality": quality,
            "market_regime": regime,
            "wallet_readmodel": wallet_read,
            "adversary_readmodel": adversary_read,
            "adversary_bridge": adversary_bridge,
            "runtime_connected": runtime_connected,
            "context_only": True,
            "can_upgrade_candidate": False,
            "hard_safety_override_allowed": False,
            "trade_permission": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
