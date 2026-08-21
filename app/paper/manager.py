import json
import logging

from datetime import (
    datetime,
    timezone,
)

from app.paper.database import (
    PaperDatabase,
)
from app.paper.cache_price import (
    CachePrice,
)
from app.risk.hybrid_exit_controller import (
    evaluate_hybrid_exit,
)
from app.risk.hybrid_exit_runtime_adapter import (
    build_hybrid_exit_runtime_input,
)
from app.strategy.mathematical_trade_plan import (
    decode_plan,
    dynamic_stop_price,
    exit_net_proceeds,
    initial_net_risk_usdt,
    mathematical_vur_kac_state,
    realization_values,
    tp1_required_fraction,
    tp2_required_fraction,
)


logger = logging.getLogger(
    __name__
)


class PaperManager:
    def __init__(
        self,
        learning_feed=None,
        hybrid_exit_evidence=None,
    ):
        self.db = PaperDatabase()
        self.price = CachePrice()

        self.learning_feed = (
            learning_feed
        )

        self.hybrid_exit_evidence = (
            hybrid_exit_evidence
        )

        self._learning_replay_after_id = 0

    @staticmethod
    def _opening_context(
        pos,
    ):
        raw = (
            pos
            or {}
        ).get(
            "opening_context_json"
        )

        if not raw:
            return None

        try:
            value = json.loads(
                raw
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return None

        return (
            value
            if isinstance(
                value,
                dict,
            )
            else None
        )

    @staticmethod
    def _json_dict(
        raw,
    ):
        if not raw:
            return {}

        try:
            value = json.loads(
                raw
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return {}

        return (
            value
            if isinstance(
                value,
                dict,
            )
            else {}
        )

    @staticmethod
    def _expected_exit_price(
        pos,
        reason,
    ):
        if reason in {
            "DYNAMIC_PROTECTION_FLOOR",
            "DYNAMIC_PROFIT_PROTECTION",
            "SEVERE_MARKET_DETERIORATION",
            "PERSISTED_STOP_LOSS",
            "MATHEMATICAL_TREND_FLOOR",
            "HARD_SAFETY_EXIT",
        }:
            value = (
                pos
                or {}
            ).get(
                "sl_price"
            )

        else:
            value = None

        try:
            value = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

        return (
            value
            if value > 0
            else None
        )

    @staticmethod
    def _is_10k_account(
        pos,
    ):
        return (
            (
                pos
                or {}
            ).get(
                "paper_account_version"
            )
            == "PAPER_10K_V2"
        )

    @staticmethod
    def _calculate_accounting(
        pos,
        current,
    ):
        token_amount = float(
            pos.get(
                "token_amount"
            )
            or 0.0
        )

        if token_amount <= 0:
            return None

        if (
            PaperManager
            ._is_10k_account(
                pos
            )
        ):
            entry_amount = float(
                pos.get(
                    "entry_amount_usdt"
                )
                or 0.0
            )

            if entry_amount <= 0:
                return None

            current_value = (
                token_amount
                * current
            )

            gross = (
                current_value
                - entry_amount
            )

            trade_value = (
                entry_amount
            )

            account = (
                "PAPER_10K_V2"
            )

        else:
            entry_amount = float(
                pos.get(
                    "amount_bnb"
                )
                or 0.0
            )

            if entry_amount <= 0:
                return None

            current_value = (
                token_amount
                * current
            )

            gross = (
                current_value
                - entry_amount
            )

            trade_value = (
                entry_amount
            )

            account = "LEGACY"

        fees = (
            float(
                pos.get(
                    "gas_buy"
                )
                or 0
            )
            + float(
                pos.get(
                    "gas_sell"
                )
                or 0
            )
            + trade_value
            * float(
                pos.get(
                    "swap_fee"
                )
                or 0
            )
            / 100
            + trade_value
            * float(
                pos.get(
                    "buy_tax"
                )
                or 0
            )
            / 100
            + trade_value
            * float(
                pos.get(
                    "sell_tax"
                )
                or 0
            )
            / 100
            + trade_value
            * float(
                pos.get(
                    "slippage"
                )
                or 0
            )
            / 100
            + trade_value
            * float(
                pos.get(
                    "mev"
                )
                or 0
            )
            / 100
        )

        net = (
            gross
            - fees
        )

        roi = (
            net
            / entry_amount
        )

        return {
            "gross": gross,
            "net": net,
            "roi": roi,

            "gross_pnl_usdt": (
                gross
                if (
                    account
                    == "PAPER_10K_V2"
                )
                else None
            ),

            "net_pnl_usdt": (
                net
                if (
                    account
                    == "PAPER_10K_V2"
                )
                else None
            ),

            "account": account,
        }

    def _observe_learning_outcome(
        self,
        pos,
        current,
        roi,
        reason,
        closed_at,
    ):
        feed = getattr(
            self,
            "learning_feed",
            None,
        )

        if feed is None:
            return None

        opening_context = (
            self._opening_context(
                pos
            )
        )

        actor_identity = (
            opening_context.get(
                "actor_identity"
            )
            if isinstance(
                opening_context,
                dict,
            )
            else None
        )

        if not isinstance(
            actor_identity,
            dict,
        ):
            actor_identity = {}

        return feed.observe_paper_close(
            position_id=pos["id"],

            token=pos["token"],

            observed_at=pos.get(
                "created_at",
                "",
            ),

            evaluated_at=closed_at,

            entry_price=pos[
                "entry_price"
            ],

            exit_price=current,

            realized_return=roi,

            close_reason=reason,

            expected_exit_price=(
                self._expected_exit_price(
                    pos,
                    reason,
                )
            ),

            opening_context=(
                opening_context
            ),

            wallet_id=(
                actor_identity.get(
                    "wallet_id"
                )
            ),

            actor_id=(
                actor_identity.get(
                    "actor_id"
                )
            ),
        )

    def replay_closed_outcomes(
        self,
    ):
        feed = getattr(
            self,
            "learning_feed",
            None,
        )

        reader = getattr(
            self.db,
            "closed_positions",
            None,
        )

        if (
            feed is None
            or reader is None
        ):
            return []

        results = []

        for pos in reader(
            after_id=(
                self._learning_replay_after_id
            )
        ):
            results.append(
                self._observe_learning_outcome(
                    pos,
                    pos.get(
                        "exit_price"
                    ),
                    pos.get(
                        "roi"
                    ),
                    pos.get(
                        "close_reason"
                    ),
                    pos.get(
                        "closed_at"
                    ),
                )
            )

            self._learning_replay_after_id = max(
                self._learning_replay_after_id,
                int(
                    pos.get(
                        "id"
                    )
                    or 0
                ),
            )

        return results

    def _hybrid_runtime_evidence(
        self,
        pos,
    ):
        source = getattr(
            self,
            "hybrid_exit_evidence",
            None,
        )

        if source is None:
            return None

        try:
            if callable(
                source
            ):
                value = source(
                    pos
                )

            elif isinstance(
                source,
                dict,
            ):
                token = (
                    pos
                    or {}
                ).get(
                    "token"
                )

                value = (
                    source.get(
                        token
                    )
                    if token in source
                    else source
                )

            else:
                return None

        except Exception as exc:
            logger.warning(
                "hybrid exit evidence unavailable "
                "position_id=%s error=%s",
                (
                    pos
                    or {}
                ).get(
                    "id"
                ),
                type(exc).__name__,
            )

            return None

        return (
            dict(value)
            if isinstance(
                value,
                dict,
            )
            else None
        )

    def _evaluate_hybrid_paper_exit(
        self,
        *,
        pos,
        current,
        highest,
    ):
        evidence = (
            self._hybrid_runtime_evidence(
                pos
            )
            or {}
        )

        signal_bundle = (
            evidence.get(
                "signal_bundle"
            )
        )

        if not isinstance(
            signal_bundle,
            dict,
        ):
            signal_bundle = {}

        runtime_input = (
            build_hybrid_exit_runtime_input(
                position_state={
                    "entry_price": (
                        pos.get(
                            "entry_price"
                        )
                    ),

                    "current_price": (
                        current
                    ),

                    "highest_price": (
                        highest
                    ),

                    "sl_price": (
                        pos.get(
                            "sl_price"
                        )
                    ),
                },

                signal_bundle=(
                    signal_bundle
                ),

                trend_health=(
                    evidence.get(
                        "trend_health"
                    )
                ),

                exit_pressure=(
                    evidence.get(
                        "exit_pressure"
                    )
                ),

                hard_block=bool(
                    evidence.get(
                        "hard_block",
                        False,
                    )
                ),

                sellability=(
                    evidence.get(
                        "sellability"
                    )
                ),
            )
        )

        keys = (
            "entry_price",
            "current_price",
            "highest_price",
            "static_sl_price",
            "hard_block",
            "sellability",
            "liquidity_health",
            "flow_momentum",
            "flow_acceleration",
            "trend_health",
            "exit_pressure",
            "price_impact_health",
            "atr_pct",
        )

        decision = evaluate_hybrid_exit(
            **{
                key: runtime_input.get(
                    key
                )
                for key in keys
            }
        )

        return {
            "decision": decision,

            "runtime_input": (
                runtime_input
            ),
        }

    def _math_accounting(
        self,
        pos,
        current,
        plan,
    ):
        entry = float(
            pos.get(
                "entry_amount_usdt"
            )
            or 0.0
        )

        tokens = float(
            pos.get(
                "token_amount"
            )
            or 0.0
        )

        realized_gross = float(
            pos.get(
                "realized_gross_proceeds_usdt"
            )
            or 0.0
        )

        realized_net = float(
            pos.get(
                "realized_proceeds_usdt"
            )
            or 0.0
        )

        gross = (
            realized_gross
            + tokens
            * current
            - entry
        )

        exit_net = (
            exit_net_proceeds(
                tokens,
                current,
                (
                    plan.get(
                        "cost_model"
                    )
                    or {}
                ),
            )
        )

        net = (
            realized_net
            + exit_net
            - entry
        )

        roi = (
            net / entry
            if entry > 0
            else 0.0
        )

        return (
            gross,
            net,
            roi,
        )

    def _close_math(
        self,
        pos,
        current,
        highest,
        lowest,
        plan,
        reason,
    ):
        (
            gross,
            net,
            roi,
        ) = self._math_accounting(
            pos,
            current,
            plan,
        )

        closed_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        close_data = {
            "current_price": (
                current
            ),

            "exit_price": (
                current
            ),

            "highest_price": (
                highest
            ),

            "lowest_price": (
                lowest
            ),

            "gross_pnl": (
                gross
            ),

            "net_pnl": (
                net
            ),

            "roi": roi,

            "gross_pnl_usdt": (
                gross
            ),

            "net_pnl_usdt": (
                net
            ),

            "close_reason": (
                reason
            ),

            "closed_at": (
                closed_at
            ),

            "token_amount": 0.0,

            "remaining_cost_basis_usdt": (
                0.0
            ),
        }

        # FINAL_REALIZED_ACCOUNTING_CONSERVATION
        entry_amount = float(
            pos.get(
                "entry_amount_usdt"
            )
            or 0.0
        )

        close_data["realized_gross_proceeds_usdt"] = (
            entry_amount
            + float(gross)
        )

        close_data["realized_proceeds_usdt"] = (
            entry_amount
            + float(net)
        )

        close_data["realized_pnl_usdt"] = float(net)

        closed = (
            self.db.close_position(
                pos["id"],
                close_data,
            )
        )

        learning = None

        if closed:
            outcome_position = dict(
                pos
            )

            outcome_position[
                "highest_price"
            ] = highest

            try:
                learning = (
                    self._observe_learning_outcome(
                        outcome_position,
                        current,
                        roi,
                        reason,
                        closed_at,
                    )
                )

            except Exception as exc:
                learning = {
                    "state": (
                        "PENDING_REPLAY"
                    ),

                    "error": (
                        type(exc).__name__
                    ),

                    "proposal_only": True,

                    "automatic_apply_allowed": (
                        False
                    ),
                }

        return {
            "success": True,
            "source": "paper",

            "data": {
                "action": (
                    "CLOSE"
                    if closed
                    else "SKIP"
                ),

                "token": (
                    pos["token"]
                ),

                "entry_price": (
                    pos[
                        "entry_price"
                    ]
                ),

                "current_price": (
                    current
                ),

                "roi": roi,

                "status": (
                    "CLOSED"
                    if closed
                    else "OPEN"
                ),

                "opened_at": (
                    pos.get(
                        "created_at",
                        "",
                    )
                ),

                "closed_at": (
                    closed_at
                    if closed
                    else ""
                ),

                "reason": (
                    reason
                    if closed
                    else (
                        "ALREADY_CLOSED"
                    )
                ),

                "account": (
                    "PAPER_10K_V2"
                ),

                "gross_pnl_usdt": (
                    gross
                ),

                "net_pnl_usdt": (
                    net
                ),

                "learning": (
                    learning
                ),

                "mathematical_exit": True,
            },
        }

    def _process_math_position(
        self,
        pos,
        current,
        highest,
        lowest,
        plan,
    ):
        self.db.record_price_observation(
            pos["id"],
            current,
        )

        post_entry_history = (
            self.db.price_observations(
                pos["id"]
            )
        )

        history = list(
            (
                plan.get(
                    "statistics"
                )
                or {}
            ).get(
                "prices"
            )
            or []
        )

        history.extend(
            post_entry_history
        )

        previous_stop = float(
            pos.get(
                "sl_price"
            )
            or 0.0
        )

        fallback_distance = (
            plan.get(
                "sl"
            )
            or {}
        ).get(
            "risk_log_distance"
        )

        new_stop = (
            dynamic_stop_price(
                prices=history,

                highest_price=(
                    highest
                ),

                previous_stop=(
                    previous_stop
                ),

                fallback_distance=(
                    fallback_distance
                ),
            )
            or previous_stop
        )

        state = (
            self._json_dict(
                pos.get(
                    "math_state_json"
                )
            )
        )

        state[
            "last_stop"
        ] = new_stop

        evidence = (
            self._hybrid_runtime_evidence(
                pos
            )
            or {}
        )

        hard_exit = bool(
            evidence.get(
                "hard_block"
            )
        ) or (
            evidence.get(
                "sellability"
            )
            is False
        )

        common_update = {
            "current_price": (
                current
            ),

            "highest_price": (
                highest
            ),

            "lowest_price": (
                lowest
            ),

            "sl_price": (
                new_stop
            ),

            "math_state_json": (
                json.dumps(
                    state,
                    sort_keys=True,
                )
            ),
        }

        if hard_exit:
            self.db.update_position(
                pos["id"],
                common_update,
            )

            return self._close_math(
                pos,
                current,
                highest,
                lowest,
                plan,
                "HARD_SAFETY_EXIT",
            )

        if (
            new_stop > 0
            and current <= new_stop
        ):
            self.db.update_position(
                pos["id"],
                common_update,
            )

            return self._close_math(
                pos,
                current,
                highest,
                lowest,
                plan,
                "MATHEMATICAL_TREND_FLOOR",
            )

        tokens = float(
            pos.get(
                "token_amount"
            )
            or 0.0
        )

        stored_basis = pos.get(
            "remaining_cost_basis_usdt"
        )

        basis = float(
            (
                pos.get(
                    "entry_amount_usdt"
                )
                or 0.0
            )
            if stored_basis is None
            else stored_basis
        )

        realized_pnl = float(
            pos.get(
                "realized_pnl_usdt"
            )
            or 0.0
        )

        realized_proceeds = float(
            pos.get(
                "realized_proceeds_usdt"
            )
            or 0.0
        )

        cost_model = (
            plan.get(
                "cost_model"
            )
            or {}
        )

        stored_initial_risk = state.get(
            "initial_net_risk_usdt"
        )

        if stored_initial_risk is None:
            initial_stop = (
                previous_stop
                if previous_stop > 0
                else None
            )

            if initial_stop is None:
                sl_plan = (
                    plan.get(
                        "sl"
                    )
                    or {}
                )

                for key in (
                    "price",
                    "stop_price",
                    "stop_loss_price",
                    "initial_stop_price",
                ):
                    try:
                        candidate_stop = float(
                            sl_plan.get(key)
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        candidate_stop = 0.0

                    if candidate_stop > 0:
                        initial_stop = (
                            candidate_stop
                        )
                        break

            initial_risk = (
                initial_net_risk_usdt(
                    token_amount=tokens,
                    entry_amount_usdt=(
                        pos.get(
                            "entry_amount_usdt"
                        )
                    ),
                    stop_price=(
                        initial_stop
                    ),
                    cost_model=(
                        cost_model
                    ),
                )
                if initial_stop
                else None
            )

            if initial_risk is None:
                initial_risk = float(
                    pos.get(
                        "risk_amount_usdt"
                    )
                    or pos.get(
                        "entry_amount_usdt"
                    )
                    or 0.0
                )

            state[
                "initial_net_risk_usdt"
            ] = float(
                initial_risk
            )

            self.db.update_position(
                pos["id"],
                {
                    "risk_amount_usdt": (
                        float(
                            initial_risk
                        )
                    ),
                    "math_state_json": (
                        json.dumps(
                            state,
                            sort_keys=True,
                        )
                    ),
                },
            )

            pos[
                "risk_amount_usdt"
            ] = float(
                initial_risk
            )
        else:
            initial_risk = float(
                stored_initial_risk
            )

        common_update[
            "risk_amount_usdt"
        ] = float(
            initial_risk
        )

        signal_bundle = (
            evidence.get(
                "signal_bundle"
            )
            if isinstance(
                evidence,
                dict,
            )
            else {}
        )

        if not isinstance(
            signal_bundle,
            dict,
        ):
            signal_bundle = {}

        vur_kac = (
            mathematical_vur_kac_state(
                prices=(
                    post_entry_history
                ),

                token_amount=(
                    tokens
                ),

                remaining_cost_basis_usdt=(
                    basis
                ),

                current_price=(
                    current
                ),

                cost_model=(
                    cost_model
                ),

                signal_bundle=(
                    signal_bundle
                ),
            )
        )

        current_ce = vur_kac.get(
            "continuation_edge_usdt"
        )

        previous_ce = state.get(
            "vur_kac_continuation_edge_usdt"
        )

        try:
            previous_ce = (
                float(previous_ce)
                if previous_ce
                is not None
                else None
            )
        except (
            TypeError,
            ValueError,
        ):
            previous_ce = None

        persistent_vur_kac = (
            bool(
                vur_kac.get(
                    "realize"
                )
            )
            and current_ce
            is not None
            and previous_ce
            is not None
            and float(current_ce)
            <= float(previous_ce)
        )

        state[
            "vur_kac_ready"
        ] = bool(
            vur_kac.get(
                "ready"
            )
        )

        state[
            "vur_kac_reason"
        ] = vur_kac.get(
            "reason"
        )

        state[
            "vur_kac_realize"
        ] = bool(
            vur_kac.get(
                "realize"
            )
        )

        state[
            "vur_kac_persistent"
        ] = bool(
            persistent_vur_kac
        )

        state[
            "vur_kac_continuation_edge_usdt"
        ] = current_ce

        state[
            "vur_kac_remaining_net_profit_usdt"
        ] = vur_kac.get(
            "remaining_net_profit_usdt"
        )

        # Once TP2 has already recovered principal,
        # the remaining inventory is the runner.
        #
        # If the mathematically negative continuation
        # edge persists or worsens for another actual
        # observation, close the remaining runner.
        if (
            int(
                pos.get(
                    "runner_active"
                )
                or 0
            )
            and persistent_vur_kac
        ):
            common_update[
                "math_state_json"
            ] = json.dumps(
                state,
                sort_keys=True,
            )

            self.db.update_position(
                pos["id"],
                common_update,
            )

            return self._close_math(
                pos,
                current,
                highest,
                lowest,
                plan,
                "MATHEMATICAL_VUR_KAC_EXIT",
            )

        stage = None
        fraction = None

        if not int(
            pos.get(
                "tp1_done"
            )
            or 0
        ):
            fraction = (
                tp1_required_fraction(
                    token_amount=tokens,

                    remaining_cost_basis_usdt=(
                        basis
                    ),

                    current_price=(
                        current
                    ),

                    initial_risk_usdt=(
                        initial_risk
                    ),

                    realized_pnl_usdt=(
                        realized_pnl
                    ),

                    cost_model=(
                        cost_model
                    ),
                )
            )

            if (
                fraction is not None
                and 0 < fraction < 1
            ):
                # First confirmed exhaustion:
                # sell only the minimum fraction
                # needed to neutralize measured
                # initial net risk.
                if bool(
                    vur_kac.get(
                        "realize"
                    )
                ):
                    stage = "TP1"

                state[
                    "tp1_required_fraction"
                ] = fraction

        elif not int(
            pos.get(
                "tp2_done"
            )
            or 0
        ):
            fraction = (
                tp2_required_fraction(
                    token_amount=tokens,

                    current_price=(
                        current
                    ),

                    original_entry_usdt=(
                        pos.get(
                            "entry_amount_usdt"
                        )
                    ),

                    realized_proceeds_usdt=(
                        realized_proceeds
                    ),

                    cost_model=(
                        cost_model
                    ),
                )
            )

            if fraction == 0:
                self.db.update_position(
                    pos["id"],
                    {
                        **common_update,

                        "tp2_done": 1,

                        "runner_active": 1,
                    },
                )

            else:
                if (
                    fraction is not None
                    and 0 < fraction < 1
                ):
                    # Continued/worsening exhaustion
                    # after TP1:
                    # sell only the minimum fraction
                    # needed to recover original entry.
                    if persistent_vur_kac:
                        stage = "TP2"

                    state[
                        "tp2_required_fraction"
                    ] = fraction

        # tp1_required_fraction / tp2_required_fraction
        # are search-state measurements. They must survive
        # a cycle even when no realization is executed yet.
        #
        # common_update was created before those state
        # measurements were calculated, so serialize the
        # current state again here.
        common_update[
            "math_state_json"
        ] = json.dumps(
            state,
            sort_keys=True,
        )

        if stage is not None:
            realization = (
                realization_values(
                    token_amount=tokens,

                    fraction=fraction,

                    current_price=(
                        current
                    ),

                    remaining_cost_basis_usdt=(
                        basis
                    ),

                    cost_model=(
                        cost_model
                    ),
                )
            )

            if (
                realization
                and (
                    self.db
                    .apply_partial_realization(
                        pos["id"],

                        stage=stage,

                        price=current,

                        realization=(
                            realization
                        ),

                        math_state_json=(
                            json.dumps(
                                state,
                                sort_keys=True,
                            )
                        ),
                    )
                )
            ):
                self.db.update_position(
                    pos["id"],
                    {
                        "highest_price": (
                            highest
                        ),

                        "lowest_price": (
                            lowest
                        ),

                        "sl_price": (
                            new_stop
                        ),
                    },
                )

                return {
                    "success": True,
                    "source": "paper",

                    "data": {
                        "action": (
                            f"PARTIAL_{stage}"
                        ),

                        "token": (
                            pos["token"]
                        ),

                        "entry_price": (
                            pos[
                                "entry_price"
                            ]
                        ),

                        "current_price": (
                            current
                        ),

                        "status": "OPEN",

                        "reason": (
                            "MATHEMATICAL_REALIZATION"
                        ),

                        "realization": (
                            realization
                        ),

                        "dynamic_sl": (
                            new_stop
                        ),

                        "runner_active": (
                            stage == "TP2"
                        ),

                        "mathematical_exit": (
                            True
                        ),
                    },
                }

        (
            gross,
            net,
            roi,
        ) = self._math_accounting(
            pos,
            current,
            plan,
        )

        self.db.update_position(
            pos["id"],
            {
                **common_update,

                "gross_pnl": gross,

                "net_pnl": net,

                "roi": roi,

                "gross_pnl_usdt": (
                    gross
                ),

                "net_pnl_usdt": (
                    net
                ),
            },
        )

        return {
            "success": True,
            "source": "paper",

            "data": {
                "action": "HOLD",

                "token": (
                    pos["token"]
                ),

                "entry_price": (
                    pos[
                        "entry_price"
                    ]
                ),

                "current_price": (
                    current
                ),

                "roi": roi,

                "status": "OPEN",

                "reason": (
                    "MATHEMATICAL_TREND_CONTINUES"
                ),

                "gross_pnl_usdt": (
                    gross
                ),

                "net_pnl_usdt": (
                    net
                ),

                "dynamic_sl": (
                    new_stop
                ),

                "tp1_done": bool(
                    pos.get(
                        "tp1_done"
                    )
                ),

                "tp2_done": bool(
                    pos.get(
                        "tp2_done"
                    )
                ),

                "runner_active": bool(
                    pos.get(
                        "runner_active"
                    )
                ),

                "mathematical_exit": True,
            },
        }

    def _process_legacy_position(
        self,
        pos,
        current,
        highest,
        lowest,
    ):
        entry = float(
            pos[
                "entry_price"
            ]
        )

        accounting = (
            self._calculate_accounting(
                pos,
                current,
            )
        )

        if accounting is None:
            return None

        gross = accounting[
            "gross"
        ]

        net = accounting[
            "net"
        ]

        roi = accounting[
            "roi"
        ]

        update = {
            "current_price": (
                current
            ),

            "highest_price": (
                highest
            ),

            "lowest_price": (
                lowest
            ),

            "gross_pnl": (
                gross
            ),

            "net_pnl": (
                net
            ),

            "roi": roi,
        }

        if (
            accounting[
                "account"
            ]
            == "PAPER_10K_V2"
        ):
            update[
                "gross_pnl_usdt"
            ] = accounting[
                "gross_pnl_usdt"
            ]

            update[
                "net_pnl_usdt"
            ] = accounting[
                "net_pnl_usdt"
            ]

        persisted_floor = float(
            pos.get(
                "sl_price"
            )
            or 0.0
        )

        action = "HOLD"

        reason = (
            "NO_EXIT_CONDITION"
        )

        hybrid_decision = None

        if (
            persisted_floor > 0
            and current
            <= persisted_floor
        ):
            action = "CLOSE"

            reason = (
                "PERSISTED_STOP_LOSS"
            )

        else:
            hybrid_result = (
                self._evaluate_hybrid_paper_exit(
                    pos=pos,

                    current=current,

                    highest=highest,
                )
            )

            hybrid_decision = (
                hybrid_result[
                    "decision"
                ]
            )

            reason = (
                hybrid_decision.reason
            )

            if (
                hybrid_decision
                .protection_price
                is not None
            ):
                raised_floor = max(
                    persisted_floor,

                    float(
                        hybrid_decision
                        .protection_price
                    ),
                )

                if raised_floor > 0:
                    update[
                        "sl_price"
                    ] = raised_floor

                    pos[
                        "sl_price"
                    ] = raised_floor

            if (
                hybrid_decision
                .exit_now
            ):
                action = "CLOSE"

        self.db.update_position(
            pos["id"],
            update,
        )

        learning_result = None

        result_closed_at = (
            pos.get(
                "closed_at",
                "",
            )
            or ""
        )

        if action == "CLOSE":
            result_closed_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            close_data = {
                "current_price": (
                    current
                ),

                "exit_price": (
                    current
                ),

                "highest_price": (
                    highest
                ),

                "lowest_price": (
                    lowest
                ),

                "gross_pnl": gross,

                "net_pnl": net,

                "roi": roi,

                "close_reason": (
                    reason
                ),

                "closed_at": (
                    result_closed_at
                ),
            }

            if (
                accounting[
                    "account"
                ]
                == "PAPER_10K_V2"
            ):
                close_data[
                    "gross_pnl_usdt"
                ] = accounting[
                    "gross_pnl_usdt"
                ]

                close_data[
                    "net_pnl_usdt"
                ] = accounting[
                    "net_pnl_usdt"
                ]

            closed = (
                self.db.close_position(
                    pos["id"],
                    close_data,
                )
            )

            if closed is False:
                action = "SKIP"
                reason = (
                    "ALREADY_CLOSED"
                )

            else:
                try:
                    outcome_position = dict(
                        pos
                    )

                    outcome_position[
                        "highest_price"
                    ] = highest

                    learning_result = (
                        self._observe_learning_outcome(
                            outcome_position,
                            current,
                            roi,
                            reason,
                            result_closed_at,
                        )
                    )

                except Exception as exc:
                    learning_result = {
                        "state": (
                            "PENDING_REPLAY"
                        ),

                        "error": (
                            type(
                                exc
                            ).__name__
                        ),

                        "proposal_only": True,

                        "automatic_apply_allowed": (
                            False
                        ),
                    }

        hybrid_payload = {
            "bound": (
                hybrid_decision
                is not None
            ),

            "decision_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

        if hybrid_decision is not None:
            hybrid_payload.update({
                "action": (
                    hybrid_decision.action
                ),

                "reason": (
                    hybrid_decision.reason
                ),

                "exit_now": (
                    hybrid_decision.exit_now
                ),

                "protect_profit": (
                    hybrid_decision
                    .protect_profit
                ),

                "runner_active": (
                    hybrid_decision
                    .runner_active
                ),

                "protection_price": (
                    hybrid_decision
                    .protection_price
                ),

                "profit_lock_price": (
                    hybrid_decision
                    .profit_lock_price
                ),

                "health_score": (
                    hybrid_decision
                    .health_score
                ),
            })

        return {
            "success": True,
            "source": "paper",

            "data": {
                "action": action,

                "token": (
                    pos["token"]
                ),

                "entry_price": (
                    entry
                ),

                "current_price": (
                    current
                ),

                "roi": roi,

                "status": (
                    "CLOSED"
                    if action == "CLOSE"
                    else "OPEN"
                ),

                "opened_at": (
                    pos.get(
                        "created_at",
                        "",
                    )
                ),

                "closed_at": (
                    result_closed_at
                ),

                "reason": reason,

                "account": (
                    accounting[
                        "account"
                    ]
                ),

                "gross_pnl_usdt": (
                    accounting[
                        "gross_pnl_usdt"
                    ]
                ),

                "net_pnl_usdt": (
                    accounting[
                        "net_pnl_usdt"
                    ]
                ),

                "learning": (
                    learning_result
                ),

                "hybrid_exit": (
                    hybrid_payload
                ),
            },
        }

    def process(self):
        self.replay_closed_outcomes()

        positions = (
            self.db.open_positions()
        )

        logger.debug(
            "Açık Pozisyon : %d",
            len(positions),
        )

        results = []

        for pos in positions:
            token = pos[
                "token"
            ]

            try:
                current = (
                    self.price
                    .get_price(
                        token
                    )
                )

            except Exception as exc:
                logger.warning(
                    "[ERROR] token=%s error=%s",
                    token,
                    exc,
                )

                continue

            highest = max(
                float(
                    pos[
                        "highest_price"
                    ]
                ),
                current,
            )

            lowest = min(
                float(
                    pos[
                        "lowest_price"
                    ]
                ),
                current,
            )

            entry = float(
                pos[
                    "entry_price"
                ]
            )

            if (
                entry <= 0
                or float(
                    pos[
                        "token_amount"
                    ]
                )
                <= 0
            ):
                continue

            plan = decode_plan(
                pos.get(
                    "mathematical_plan_json"
                )
            )

            if (
                plan
                and plan.get(
                    "contract"
                )
                == (
                    "mathematical_trade_plan"
                )
            ):
                result = (
                    self._process_math_position(
                        pos,
                        current,
                        highest,
                        lowest,
                        plan,
                    )
                )

            else:
                # Legacy compatibility only.
                # New positions are created
                # with mathematical_plan_json.
                result = (
                    self._process_legacy_position(
                        pos,
                        current,
                        highest,
                        lowest,
                    )
                )

            if result is not None:
                results.append(
                    result
                )

        return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG
    )

    PaperManager().process()
