from collections import Counter, OrderedDict

from app.dex.adversary_evidence import (
    adversary_evidence,
)
from app.dex.adversary_reputation import (
    evaluate_adversary_reputation,
)
from app.dex.entity_linking import (
    build_entity_link,
)
from app.dex.transaction_origin import (
    TransactionOriginResolver,
)
from app.dex.wallet_behavior import (
    classify_wallet_behavior,
)
from app.dex.wallet_evidence import (
    wallet_evidence,
)
from app.dex.wallet_reputation import (
    evaluate_wallet_reputation,
)
from app.dex.wash_sybil_intelligence import (
    evaluate_wash_sybil,
)


def _address(value):
    if value is None:
        return None

    value = (
        str(value)
        .strip()
        .lower()
    )

    return value or None


class RuntimeActorIntelligence:
    """
    Real runtime actor producer.

    Identity source:
        transaction.from only

    Does NOT claim:
    - router Swap sender == user wallet
    - institutional identity
    - multi-wallet entity proof
    - whale value without comparable value evidence
    - scam/MEV/pump-dump evidence without matching evidence
    """

    def __init__(
        self,
        *,
        chain="bsc",
        max_pairs=256,
        max_events_per_pair=2048,
        resolver=None,
        wallet_writer=None,
        adversary_writer=None,
    ):
        self.chain = (
            str(chain or "")
            .strip()
            .lower()
        )

        if not self.chain:
            raise ValueError(
                "chain required"
            )

        self.max_pairs = max(
            1,
            int(max_pairs),
        )

        self.max_events_per_pair = max(
            1,
            int(max_events_per_pair),
        )

        self.resolver = (
            resolver
            or TransactionOriginResolver()
        )

        self.wallet_writer = (
            wallet_writer
        )

        self.adversary_writer = (
            adversary_writer
        )

        self._pairs = OrderedDict()
        self._events = {}
        self._latest_actor = {}

        self.accepted_events = 0
        self.retracted_events = 0
        self.unresolved_origins = 0
        self.dropped_events = 0

    @property
    def pair_count(self):
        return len(
            self._pairs
        )

    @property
    def event_count(self):
        return sum(
            len(v)
            for v in self._events.values()
        )

    async def observe_event(
        self,
        event,
        *,
        direction="UNKNOWN",
    ):
        event = dict(
            event or {}
        )

        pair = _address(
            event.get("address")
        )

        identity = event.get(
            "event_identity"
        )

        transaction_hash = (
            event.get(
                "transaction_hash"
            )
        )

        if (
            not pair
            or not identity
            or not transaction_hash
        ):
            return {
                "state": "IGNORED",
                "reason": (
                    "PAIR_OR_IDENTITY_MISSING"
                ),
            }

        resolved = await self.resolver.resolve(
            transaction_hash
        )

        if resolved.get(
            "state"
        ) != "READY":
            self.unresolved_origins += 1

            return {
                "state": "UNKNOWN",
                "reason": (
                    "TX_ORIGIN_UNRESOLVED"
                ),
                "transaction_origin": (
                    resolved
                ),
                "identity_guessing": False,
                "decision_authority": False,
                "execution_authority": False,
            }

        address = resolved[
            "address"
        ]

        wallet_id = (
            f"{self.chain}:{address}"
        )

        self._ensure_pair(
            pair
        )

        events = self._events[
            pair
        ]

        if identity in events:
            events.pop(
                identity,
                None,
            )

        events[
            identity
        ] = {
            "event_identity": identity,
            "transaction_hash": (
                str(transaction_hash)
                .lower()
            ),
            "wallet_id": wallet_id,
            "address": address,
            "direction": (
                direction
                if direction
                in {"BULL", "BEAR"}
                else "UNKNOWN"
            ),
            "block_number": (
                event.get(
                    "block_number"
                )
            ),
            "log_index": (
                event.get(
                    "log_index"
                )
            ),
        }

        while (
            len(events)
            > self.max_events_per_pair
        ):
            events.popitem(
                last=False
            )

            self.dropped_events += 1

        self._latest_actor[
            pair
        ] = wallet_id

        self.accepted_events += 1

        payload = self._build_for_wallet(
            pair,
            wallet_id,
        )

        self._write_payloads(
            wallet_id,
            payload,
        )

        return {
            "state": "OBSERVED",
            "pair": pair,
            "wallet_id": wallet_id,
            "adversary_key": (
                wallet_id
            ),
            "transaction_origin": (
                resolved
            ),
            "wallet_context": (
                payload[
                    "wallet_context"
                ]
            ),
            "adversary_reputation": (
                payload[
                    "adversary_reputation"
                ]
            ),
            "identity_guessing": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    async def observe_retraction(
        self,
        event,
    ):
        event = dict(
            event or {}
        )

        pair = _address(
            event.get("address")
        )

        identity = (
            event.get(
                "retracts_event_identity"
            )
            or event.get(
                "event_identity"
            )
        )

        if (
            not pair
            or pair not in self._events
            or not identity
        ):
            return {
                "state": "IGNORED"
            }

        removed = self._events[
            pair
        ].pop(
            identity,
            None,
        )

        if removed is None:
            return {
                "state": "NOT_FOUND",
                "event_identity": identity,
            }

        self.retracted_events += 1

        wallet_id = removed[
            "wallet_id"
        ]

        transaction_hash = removed.get(
            "transaction_hash"
        )

        if transaction_hash:
            self.resolver.forget(
                transaction_hash
            )

        remaining_for_wallet = [
            row
            for row
            in self._events[
                pair
            ].values()
            if (
                row.get(
                    "wallet_id"
                )
                == wallet_id
            )
        ]

        if remaining_for_wallet:
            payload = (
                self._build_for_wallet(
                    pair,
                    wallet_id,
                )
            )

            self._write_payloads(
                wallet_id,
                payload,
            )

        else:
            self._write_retracted(
                wallet_id
            )

        pair_events = list(
            self._events[
                pair
            ].values()
        )

        if pair_events:
            self._latest_actor[
                pair
            ] = pair_events[
                -1
            ][
                "wallet_id"
            ]
        else:
            self._latest_actor.pop(
                pair,
                None,
            )

        return {
            "state": "RETRACTED",
            "event_identity": (
                identity
            ),
            "wallet_id": wallet_id,
            "decision_authority": False,
            "execution_authority": False,
        }

    def snapshot(
        self,
        pair,
    ):
        pair = _address(pair)

        wallet_id = (
            self._latest_actor.get(
                pair
            )
            if pair
            else None
        )

        if not wallet_id:
            return {
                "state": "UNKNOWN",
                "wallet_id": None,
                "adversary_key": None,
                "identity_source": (
                    "TRANSACTION_FROM_ONLY"
                ),
                "identity_guessing": False,
                "decision_authority": False,
                "execution_authority": False,
            }

        return {
            "state": "READY",
            "wallet_id": wallet_id,
            "adversary_key": (
                wallet_id
            ),
            "identity_source": (
                "TRANSACTION_FROM_ONLY"
            ),
            "identity_guessing": False,
            "decision_authority": False,
            "execution_authority": False,
        }

    def _ensure_pair(
        self,
        pair,
    ):
        if pair in self._pairs:
            self._pairs.move_to_end(
                pair
            )
            return

        if (
            len(self._pairs)
            >= self.max_pairs
        ):
            oldest, _ = (
                self._pairs.popitem(
                    last=False
                )
            )

            self._events.pop(
                oldest,
                None,
            )

            self._latest_actor.pop(
                oldest,
                None,
            )

        self._pairs[
            pair
        ] = True

        self._events[
            pair
        ] = OrderedDict()

    def _build_for_wallet(
        self,
        pair,
        wallet_id,
    ):
        rows = list(
            self._events[
                pair
            ].values()
        )

        wallet_rows = [
            row
            for row in rows
            if row.get(
                "wallet_id"
            )
            == wallet_id
        ]

        address = wallet_id.split(
            ":",
            1,
        )[1]

        buys = sum(
            row.get("direction")
            == "BULL"
            for row in wallet_rows
        )

        sells = sum(
            row.get("direction")
            == "BEAR"
            for row in wallet_rows
        )

        interactions = len(
            wallet_rows
        )

        evidence = wallet_evidence(
            self.chain,
            address,
            inbound_value=0,
            outbound_value=0,
            buy_count=buys,
            sell_count=sells,
            freshness="FRESH",
        )

        behavior = (
            classify_wallet_behavior(
                buy_count=buys,
                sell_count=sells,
                inbound_value=0,
                outbound_value=0,
                interaction_count=(
                    interactions
                ),
                recent_activity_count=(
                    interactions
                ),
                previous_activity_count=0,
                freshness="FRESH",
            )
        )

        # Conservative self-only entity scope.
        # This does NOT merge different wallets.
        entity = build_entity_link(
            wallet_id=wallet_id,
            entity_id=(
                f"self:{wallet_id}"
            ),
            evidence_count=(
                interactions
            ),
            confidence=1.0,
            ambiguous=False,
            source_fresh=True,
        )

        total_pair_events = len(
            rows
        )

        wallet_share = (
            interactions
            / total_pair_events
            if total_pair_events > 0
            else 0.0
        )

        # Minimum sample guard:
        # one/few transactions cannot create
        # concentration reputation.
        concentration = (
            wallet_share
            if total_pair_events >= 5
            else 0.0
        )

        reputation = (
            evaluate_wallet_reputation(
                repeat_offender_count=0,
                coordination_score=0.0,
                concentration_score=(
                    concentration
                ),
                hard_evidence=False,
                soft_age=0,
                freshness="FRESH",
            )
        )

        actor_counts = Counter(
            row.get("wallet_id")
            for row in rows
            if row.get(
                "wallet_id"
            )
        )

        unique_wallets = len(
            actor_counts
        )

        independent_ratio = (
            unique_wallets
            / total_pair_events
            if total_pair_events > 0
            else 0.0
        )

        independent_ratio = max(
            0.0,
            min(
                1.0,
                independent_ratio,
            ),
        )

        wash = evaluate_wash_sybil(
            wallet_count=(
                unique_wallets
            ),
            repeated_counterparty_ratio=0.0,
            circular_flow_ratio=0.0,
            coordination_score=0.0,
            independent_wallet_ratio=(
                independent_ratio
            ),
            freshness="FRESH",
        )

        adv_evidence = adversary_evidence(
            chain=self.chain,
            actor_id=address,
            evidence_type=(
                "RUNTIME_PARTICIPATION"
            ),
            evidence_count=(
                interactions
            ),
            confidence=(
                min(
                    0.70,
                    interactions / 10.0,
                )
            ),
            freshness="FRESH",
            provenance=(
                "NATIVE_WSS_TX_FROM"
            ),
        )

        adversary = (
            evaluate_adversary_reputation(
                mev_state=(
                    "LOW_OR_UNRESOLVED_MEV_RISK"
                ),
                scam_state="NONE",
                wash_state=wash.get(
                    "state",
                    "NONE",
                ),
                pumpdump_state="NONE",
                repeat_offender_count=0,
                hard_evidence=False,
                soft_age=0,
                conflicting_evidence=False,
                freshness="FRESH",
            )
        )

        wallet_context = {
            "state": "READY",
            "wallet_context_ready": True,
            "wallet_id": wallet_id,
            "market_context_allowed": True,
            "wallet_hard_risk": (
                reputation.get(
                    "state"
                )
                == "HARD_RISK_EVIDENCE"
            ),
            "identity_source": (
                "TRANSACTION_FROM_ONLY"
            ),
            "identity_guessing": False,
            "swap_sender_is_wallet": False,
            "behavior_state": (
                behavior.get(
                    "state",
                    "UNKNOWN",
                )
            ),
            "behavior_tags": (
                behavior.get(
                    "behavior_tags",
                    [],
                )
            ),
            "entity_state": (
                entity.get(
                    "state",
                    "UNKNOWN",
                )
            ),
            "entity_scope": (
                "SELF_ONLY_NO_CROSS_WALLET_MERGE"
            ),
            "entity_auto_merge": False,
            "entity_identity_proof": False,
            "whale_state": "UNKNOWN",
            "whale_value_evidence_ready": False,
            "reputation_state": (
                reputation.get(
                    "state",
                    "UNKNOWN",
                )
            ),
            "reputation_score": (
                reputation.get(
                    "risk_score"
                )
            ),
            "interaction_count": (
                interactions
            ),
            "buy_count": buys,
            "sell_count": sells,
            "pair_event_share": (
                wallet_share
            ),
            "hard_safety_override_allowed": False,
            "trade_permission": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

        return {
            "wallet_context": (
                wallet_context
            ),
            "wallet_evidence": (
                evidence
            ),
            "wallet_behavior": (
                behavior
            ),
            "entity_link": entity,
            "wallet_reputation": (
                reputation
            ),
            "wash_sybil": wash,
            "adversary_evidence": (
                adv_evidence
            ),
            "adversary_reputation": (
                adversary
            ),
        }

    def _write_payloads(
        self,
        wallet_id,
        payload,
    ):
        if self.wallet_writer:
            self.wallet_writer(
                wallet_id,
                payload[
                    "wallet_context"
                ],
            )

        if self.adversary_writer:
            self.adversary_writer(
                wallet_id,
                payload[
                    "adversary_reputation"
                ],
            )

    def _write_retracted(
        self,
        wallet_id,
    ):
        if self.wallet_writer:
            self.wallet_writer(
                wallet_id,
                {
                    "state": "RETRACTED",
                    "wallet_context_ready": False,
                    "wallet_id": wallet_id,
                    "market_context_allowed": False,
                    "wallet_hard_risk": False,
                    "identity_source": (
                        "TRANSACTION_FROM_ONLY"
                    ),
                    "identity_guessing": False,
                    "hard_safety_override_allowed": False,
                    "trade_permission": False,
                    "decision_authority": False,
                    "execution_authority": False,
                },
            )

        if self.adversary_writer:
            self.adversary_writer(
                wallet_id,
                {
                    "state": "UNKNOWN",
                    "risk_score": 0.0,
                    "hard_evidence": False,
                    "evidence_tags": [],
                    "trade_permission": False,
                    "decision_authority": False,
                    "execution_authority": False,
                },
            )

    def status(self):
        return {
            "state": "READY",
            "pair_count": (
                self.pair_count
            ),
            "event_count": (
                self.event_count
            ),
            "max_pairs": (
                self.max_pairs
            ),
            "max_events_per_pair": (
                self.max_events_per_pair
            ),
            "accepted_events": (
                self.accepted_events
            ),
            "retracted_events": (
                self.retracted_events
            ),
            "unresolved_origins": (
                self.unresolved_origins
            ),
            "dropped_events": (
                self.dropped_events
            ),
            "resolver": (
                self.resolver.status()
            ),
            "identity_source": (
                "TRANSACTION_FROM_ONLY"
            ),
            "swap_sender_is_wallet": False,
            "cross_wallet_auto_merge": False,
            "whale_value_invented": False,
            "scam_evidence_invented": False,
            "mev_evidence_invented": False,
            "pumpdump_evidence_invented": False,
            "bounded": True,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
