from collections import OrderedDict

from app.learning.outcome_evidence import (
    build_outcome_evidence,
)
from app.learning.outcome_classification import (
    classify_outcome,
)
from app.learning.signal_attribution import (
    attribute_signals,
)
from app.learning.entry_context import (
    to_outcome_relative_states,
)
from app.learning.outcome_memory import (
    OutcomeMemory,
)
from app.learning.calibration_statistics import (
    build_calibration_statistics,
)
from app.learning.calibration_proposal import (
    build_calibration_proposal,
)
from app.learning.calibration_readmodel import (
    CalibrationReadModel,
    build_calibration_bucket,
)

from app.learning.outcome_segmentation import (
    build_outcome_segments,
)


class RuntimeLearningOutcomeFeed:
    """
    Real paper-close -> Phase 11 learning adapter.

    Scope:
    - completed PAPER positions only
    - proposal-only learning
    - bounded runtime memory/readmodel
    - no hindsight reconstruction
    - no config/threshold/weight apply
    - no trade/execution authority
    """

    def __init__(
        self,
        *,
        chain="bsc",
        max_events=4096,
        max_memory=2048,
        max_readmodel=256,
        min_samples=20,
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

        self.max_events = max(
            1,
            int(max_events),
        )

        self.min_samples = max(
            1,
            int(min_samples),
        )

        self._events = OrderedDict()

        self.memory = OutcomeMemory(
            max_entries=max_memory
        )

        self.readmodel = (
            CalibrationReadModel(
                max_entries=max_readmodel
            )
        )

        self.accepted_count = 0
        self.duplicate_count = 0
        self.unknown_count = 0
        self.dropped_count = 0

    @property
    def event_count(self):
        return len(self._events)

    def observe_paper_close(
        self,
        *,
        position_id,
        token,
        observed_at,
        evaluated_at,
        entry_price,
        exit_price,
        realized_return,
        close_reason,
        expected_exit_price=None,
        opening_context=None,
        wallet_id=None,
        actor_id=None,
        market_regime=None,
    ):
        observation_id = (
            f"paper-position:{position_id}"
            if position_id is not None
            else None
        )

        if not observation_id:
            return self._out(
                "INVALID",
                None,
            )

        outcome_id = (
            f"{self.chain}:"
            f"{observation_id}"
        )

        if outcome_id in self._events:
            self.duplicate_count += 1

            return self._out(
                "DUPLICATE",
                self._events[
                    outcome_id
                ],
            )

        realized = self._realized(
            entry_price=entry_price,
            exit_price=exit_price,
            realized_return=realized_return,
            close_reason=close_reason,
            expected_exit_price=(
                expected_exit_price
            ),
        )

        evidence_complete = bool(
            observed_at
            and evaluated_at
            and token
            and realized[
                "return"
            ] is not None
        )

        evidence = build_outcome_evidence(
            chain=self.chain,
            observation_id=observation_id,
            observed_at=observed_at,
            evaluated_at=evaluated_at,
            expected_context={
                "position_type": "PAPER",
                "historical_signal": "POSITIVE",
                "historical_action": "ALLOW",
                "opening_context": (
                    opening_context
                ),
            },
            realized_outcome=(
                realized
                if evidence_complete
                else None
            ),
            evidence_coverage=(
                1.0
                if evidence_complete
                else 0.0
            ),
            freshness="FRESH",
            provenance=(
                "PAPER_MANAGER_CLOSE"
            ),
        )

        classification = (
            classify_outcome(
                signal_state="POSITIVE",
                candidate_action="ALLOW",
                realized_direction=(
                    realized[
                        "direction"
                    ]
                ),
                realized_return=(
                    realized[
                        "return"
                    ]
                ),
                exit_failed=False,
                evidence_complete=(
                    evidence_complete
                ),
                freshness="FRESH",
            )
        )

        outcome_class = (
            classification[
                "outcome_class"
            ]
        )

        # We do NOT reconstruct historical signal-family
        # attribution from current state. If opening-time
        # attribution wasn't persisted, it remains UNKNOWN.
        signal_states = {}

        if isinstance(
            opening_context,
            dict,
        ):
            raw = opening_context.get(
                "signal_attribution"
            )

            if isinstance(
                raw,
                dict,
            ):
                signal_states = dict(
                    raw
                )

        attribution = attribute_signals(
            outcome_class=outcome_class,
            signal_states=(
                to_outcome_relative_states(
                    outcome_class=(
                        outcome_class
                    ),
                    entry_signal_states=(
                        signal_states
                        or {
                            "paper_entry": (
                                "UNKNOWN"
                            )
                        }
                    ),
                )
            ),
            hard_safety_signals=[],
            freshness="FRESH",
            evidence_complete=(
                evidence_complete
            ),
        )

        memory_result = self.memory.add(
            outcome_id=outcome_id,
            outcome_class=outcome_class,
            chain=self.chain,
            token=token,
            wallet_id=wallet_id,
            entity_id=None,
            actor_id=actor_id,
            market_regime=market_regime,
            signal_family="paper_entry",
            freshness="FRESH",
        )

        row = {
            "outcome_id": outcome_id,
            "position_id": position_id,
            "token": token,
            "observed_at": observed_at,
            "evaluated_at": evaluated_at,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "realized_return": (
                realized[
                    "return"
                ]
            ),
            "realized_direction": (
                realized[
                    "direction"
                ]
            ),
            "close_reason": (
                close_reason
            ),
            "expected_exit_price": (
                realized[
                    "expected_exit_price"
                ]
            ),
            "exit_price_drift_ratio": (
                realized[
                    "exit_price_drift_ratio"
                ]
            ),
            "exit_price_drift_available": (
                realized[
                    "exit_price_drift_available"
                ]
            ),
            "evidence": evidence,
            "classification": (
                classification
            ),
            "attribution": attribution,
            "memory_result": (
                memory_result
            ),
            "opening_context_persisted": (
                opening_context
                is not None
            ),
            "hindsight_rewrite_allowed": False,
            "proposal_only": True,
            "automatic_apply_allowed": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

        self._events[
            outcome_id
        ] = row

        while (
            len(self._events)
            > self.max_events
        ):
            self._events.popitem(
                last=False
            )

            self.dropped_count += 1

        self.accepted_count += 1

        if outcome_class == "UNKNOWN":
            self.unknown_count += 1

        calibration = (
            self._rebuild_calibration()
        )

        row[
            "calibration"
        ] = calibration

        return self._out(
            "OBSERVED",
            row,
        )

    def event_snapshot(self):
        return [
            dict(row)
            for row in self._events.values()
        ]

    def calibration_snapshot(self):
        return self.readmodel.get(
            "paper:closed_positions"
        )

    def _rebuild_calibration(self):
        counts = {
            "VALID_SIGNAL": 0,
            "FALSE_POSITIVE": 0,
            "FALSE_NEGATIVE": 0,
            "AVOIDED_LOSS": 0,
            "MISSED_OPPORTUNITY": 0,
            "EXIT_FAILURE": 0,
            "UNKNOWN": 0,
        }

        for row in self._events.values():
            outcome_class = (
                row.get(
                    "classification",
                    {},
                ).get(
                    "outcome_class",
                    "UNKNOWN",
                )
            )

            if outcome_class not in counts:
                outcome_class = (
                    "UNKNOWN"
                )

            counts[
                outcome_class
            ] += 1

        total = sum(
            counts.values()
        )

        known = (
            total
            - counts["UNKNOWN"]
        )

        coverage = (
            known / total
            if total > 0
            else 0.0
        )

        stats = (
            build_calibration_statistics(
                valid_signal_count=(
                    counts[
                        "VALID_SIGNAL"
                    ]
                ),
                false_positive_count=(
                    counts[
                        "FALSE_POSITIVE"
                    ]
                ),
                false_negative_count=(
                    counts[
                        "FALSE_NEGATIVE"
                    ]
                ),
                avoided_loss_count=(
                    counts[
                        "AVOIDED_LOSS"
                    ]
                ),
                missed_opportunity_count=(
                    counts[
                        "MISSED_OPPORTUNITY"
                    ]
                ),
                exit_failure_count=(
                    counts[
                        "EXIT_FAILURE"
                    ]
                ),
                unknown_count=(
                    counts[
                        "UNKNOWN"
                    ]
                ),
                evidence_coverage=coverage,
                freshness="FRESH",
                min_samples=(
                    self.min_samples
                ),
            )
        )

        weight = (
            build_calibration_proposal(
                stats,
                target="WEIGHT",
            )
        )

        threshold = (
            build_calibration_proposal(
                stats,
                target="THRESHOLD",
            )
        )

        bucket = build_calibration_bucket(
            statistics=stats,
            proposal=weight,
            freshness="FRESH",
        )

        segmentation = build_outcome_segments(
            self._events.values(),
            min_samples=self.min_samples,
        )

        payload = {
            **bucket,
            "segmentation": segmentation,
            "statistics": stats,
            "weight_proposal": weight,
            "threshold_proposal": (
                threshold
            ),
            "source": (
                "REAL_PAPER_CLOSED_POSITIONS"
            ),
            "proposal_only": True,
            "automatic_apply_allowed": False,
            "config_write_allowed": False,
            "threshold_write_allowed": False,
            "weight_write_allowed": False,
            "strategy_rewrite_allowed": False,
            "source_code_edit_allowed": False,
            "hard_safety_weakening_allowed": False,
            "ai_authority": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

        self.readmodel.put(
            "paper:closed_positions",
            payload,
        )

        return payload

    @staticmethod
    def _realized(
        *,
        entry_price,
        exit_price,
        realized_return,
        close_reason,
        expected_exit_price=None,
    ):
        try:
            ret = float(
                realized_return
            )
        except (
            TypeError,
            ValueError,
        ):
            ret = None

        if ret is not None:
            if ret > 0:
                direction = "UP"
            elif ret < 0:
                direction = "DOWN"
            else:
                direction = "FLAT"
        else:
            direction = "UNKNOWN"

        try:
            expected = float(
                expected_exit_price
            )
        except (
            TypeError,
            ValueError,
        ):
            expected = None

        try:
            actual_exit = float(
                exit_price
            )
        except (
            TypeError,
            ValueError,
        ):
            actual_exit = None

        if (
            expected is not None
            and expected > 0
            and actual_exit is not None
        ):
            exit_drift = (
                actual_exit / expected
                - 1.0
            )
        else:
            expected = None
            exit_drift = None

        return {
            "entry_price": (
                entry_price
            ),
            "exit_price": (
                exit_price
            ),
            "return": ret,
            "direction": direction,
            "expected_exit_price": (
                expected
            ),
            "exit_price_drift_ratio": (
                exit_drift
            ),
            "exit_price_drift_available": (
                exit_drift is not None
            ),
            "close_reason": (
                close_reason
            ),
        }

    def status(self):
        return {
            "state": "READY",
            "event_count": (
                self.event_count
            ),
            "max_events": (
                self.max_events
            ),
            "memory_size": (
                self.memory.size
            ),
            "readmodel_size": (
                self.readmodel.size
            ),
            "accepted_count": (
                self.accepted_count
            ),
            "duplicate_count": (
                self.duplicate_count
            ),
            "unknown_count": (
                self.unknown_count
            ),
            "dropped_count": (
                self.dropped_count
            ),
            "bounded": True,
            "source": (
                "REAL_PAPER_CLOSE"
            ),
            "proposal_only": True,
            "automatic_apply_allowed": False,
            "config_write_allowed": False,
            "threshold_write_allowed": False,
            "weight_write_allowed": False,
            "strategy_rewrite_allowed": False,
            "source_code_edit_allowed": False,
            "hard_safety_weakening_allowed": False,
            "ai_authority": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    @staticmethod
    def _out(
        state,
        payload,
    ):
        return {
            "state": state,
            "payload": payload,
            "proposal_only": True,
            "automatic_apply_allowed": False,
            "decision_authority": False,
            "execution_authority": False,
        }
