import json
import logging
import threading

from app.pipeline.market_context import build_market_context
from app.scanner.adapters.source_router import normalize_source_rows


logger = logging.getLogger(__name__)

FAST_WATCH_REASONS = {
    "ACTIVE_PRICE_SERIES_NOT_READY",
    "ACTIVE_MOMENTUM_NOT_POSITIVE",
    "POSITIVE_CONTINUATION_NOT_ESTABLISHED",
}

FAST_WATCH_MAX_CANDIDATES = 30


class FastWatchRevisitJob:
    """
    Re-evaluate recent structural PAPER_BUY candidates that are waiting only
    on active price-continuation evidence.

    No alternate strategy/admission path is introduced. Every selected row is
    re-admitted through the canonical ingress gate and sent through
    PipelineEngine.run(), then through the existing durable counterfactual
    observer. The scheduled trigger is non-blocking so slow provider/RPC work
    cannot delay paper-manager or watch-probe exit jobs. Hard risk,
    sellability, opportunity, sizing and paper-position guards remain
    canonical. Live/wallet/execution authority is unchanged.
    """

    def __init__(
        self,
        pipeline,
        *,
        max_candidates=FAST_WATCH_MAX_CANDIDATES,
    ):
        self.pipeline = pipeline
        self.max_candidates = max(
            1,
            int(max_candidates),
        )
        self._state_lock = threading.Lock()
        self._running = False
        self._thread = None
        self.last_status = self._status(
            state="IDLE",
        )

    @staticmethod
    def _canonical(value):
        value = str(value or "").strip().lower()
        if value.startswith("bsc_"):
            value = value[4:]
        return value

    def _status(
        self,
        *,
        state,
        selected=0,
        processed=0,
        failed=0,
        paper_buys=0,
    ):
        return {
            "state": state,
            "selected": int(selected),
            "processed": int(processed),
            "failed": int(failed),
            "paper_buys": int(paper_buys),
            "bounded": True,
            "max_candidates": self.max_candidates,
            "decision_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def _has_trade_history(self, token):
        databases = []

        direct = getattr(
            self.pipeline,
            "paper_db",
            None,
        )
        if direct is not None:
            databases.append(direct)

        manager = getattr(
            self.pipeline,
            "manager",
            None,
        )
        manager_db = getattr(
            manager,
            "db",
            None,
        )
        if (
            manager_db is not None
            and manager_db not in databases
        ):
            databases.append(manager_db)

        for database in databases:
            reader = getattr(
                database,
                "has_trade_history",
                None,
            )
            if not callable(reader):
                continue

            try:
                if reader(token):
                    return True
            except Exception:
                logger.exception(
                    "Fast watch trade-history check failed token=%s",
                    token,
                )
                return True

        return False

    def _watched_identities(self):
        store = getattr(
            self.pipeline,
            "counterfactual_store",
            None,
        )
        snapshot = getattr(
            store,
            "decision_snapshot",
            None,
        )

        if not callable(snapshot):
            return []

        rows = snapshot(
            limit=max(
                self.max_candidates * 8,
                self.max_candidates,
            )
        )

        selected = []
        seen = set()

        for item in rows or []:
            if len(selected) >= self.max_candidates:
                break

            token = self._canonical(
                item.get("token")
            )
            pool = self._canonical(
                item.get("pool")
            )
            identity = (token, pool)

            if not token or not pool or identity in seen:
                continue

            # decision_snapshot() is newest-first. Mark the identity seen
            # before checking action/reason so an older WATCH can never
            # override a newer REJECT/non-WATCH transition.
            seen.add(identity)

            action = str(
                item.get("decision_action")
                or ""
            ).upper()
            if action != "WATCH":
                continue

            if self._has_trade_history(token):
                continue

            try:
                context = json.loads(
                    item.get("context_json")
                    or "{}"
                )
            except (
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                continue

            if str(
                context.get("strategy")
                or ""
            ).upper() != "PAPER_BUY":
                continue

            if str(
                context.get("opportunity_reason")
                or ""
            ).upper() not in FAST_WATCH_REASONS:
                continue

            if bool(context.get("hard_block")):
                continue

            selected.append(identity)

        return selected

    def _cache_rows(self, identities):
        cache = getattr(
            self.pipeline,
            "cache",
            None,
        )
        reader = getattr(
            cache,
            "all",
            None,
        )
        ingress_gate = getattr(
            self.pipeline,
            "ingress_gate",
            None,
        )
        classify_many = getattr(
            ingress_gate,
            "classify_many",
            None,
        )

        # Fast revisit must fail closed if the canonical ingress gate is not
        # available. It must never become an admission bypass.
        if (
            not callable(reader)
            or not callable(classify_many)
        ):
            return []

        wanted = set(identities)
        selected = []

        for row in reader() or []:
            token = self._canonical(
                row.get("token")
            )
            pool = self._canonical(
                row.get("pool")
            )

            if (token, pool) not in wanted:
                continue

            normalized = normalize_source_rows(
                "geckoterminal",
                "bsc",
                [row],
            )

            candidates = normalized.get(
                "candidates",
                [],
            )

            if not candidates:
                continue

            candidate = candidates[0].to_dict()
            ingress = classify_many(
                [candidate]
            )
            active = ingress.get(
                "active",
                [],
            )

            if active:
                selected.append(
                    active[0]
                )

        return selected

    def _process(self, row):
        runtime_feed = getattr(
            self.pipeline,
            "native_market_flow",
            None,
        )

        confirm_pair = getattr(
            runtime_feed,
            "confirm_pair_membership",
            None,
        )

        if callable(confirm_pair):
            confirm_pair(
                row.get("pool"),
                row.get("token"),
                row.get("quote_token"),
            )

        market_context = build_market_context(
            row,
            runtime_feed=runtime_feed,
        )
        market_context["candidate_pool"] = row.get(
            "pool"
        )
        market_context[
            "candidate_quote_token"
        ] = row.get("quote_token")

        actor_runtime = getattr(
            self.pipeline,
            "native_actor_intelligence",
            None,
        )

        if actor_runtime is not None:
            actor_snapshot = actor_runtime.snapshot(
                row.get("pool")
            )

            if actor_snapshot.get("state") == "READY":
                market_context["wallet_id"] = actor_snapshot[
                    "wallet_id"
                ]
                market_context[
                    "adversary_key"
                ] = actor_snapshot[
                    "adversary_key"
                ]
                market_context["runtime_actor"] = actor_snapshot

        result = self.pipeline.run(
            row["token"],
            market_context=market_context,
        )

        data = result.get("data", {})
        strategy = data.get("strategy") or {}
        unified = data.get("unified_decision") or {}
        paper = data.get("paper") or {}
        score = data.get("unified_score") or {}
        risk_gate = data.get("risk_gate") or {}
        analyzer_status = data.get("analyzer_status") or {}

        summary = {
            "token": row.get("token"),
            "pool": row.get("pool"),
            "strategy": strategy.get("decision"),
            "unified": unified.get("decision"),
            "paper": paper.get("action"),
            "reason": paper.get("reason"),
            "opportunity_state": score.get(
                "opportunity_state"
            ),
            "opportunity_reason": score.get(
                "opportunity_reason"
            ),
            "plan_blockers": list(
                paper.get("plan_blockers")
                or []
            ),
            "sizing_blockers": list(
                paper.get("sizing_blockers")
                or []
            ),
            "sizing_reason": paper.get(
                "sizing_reason"
            ),
            "entry_amount_usdt": paper.get(
                "entry_amount_usdt"
            ),
            "mathematical_plan": paper.get(
                "mathematical_plan"
            ),
            "sizing_diagnostics": dict(
                paper.get("sizing_diagnostics")
                or {}
            ),
            "vur_kac_entry_shadow": dict(
                paper.get("vur_kac_entry_shadow")
                or {}
            ),
            "hard_block": bool(
                risk_gate.get("hard_block")
            ),
            "score": score.get("score"),
            "confidence": score.get("confidence"),
            "sellability": (
                analyzer_status.get(
                    "sellability",
                    {},
                ).get("status")
            ),
            "market_context": (
                data.get("market_context")
                or market_context
            ),
            "runtime_intelligence": (
                data.get("runtime_intelligence")
                or {}
            ),
        }

        observer = getattr(
            self.pipeline,
            "observe_counterfactual_candidate",
            None,
        )
        if callable(observer):
            observed_row = dict(row)
            current_price = (
                summary["market_context"].get("price_usd")
                if isinstance(summary["market_context"], dict)
                else None
            )
            if current_price is not None:
                observed_row["price_usd"] = current_price

            observer(
                observed_row,
                summary,
            )

        logger.info(
            (
                "Fast watch revisit token=%s pool=%s "
                "paper=%s opportunity=%s opportunity_reason=%s"
            ),
            summary["token"],
            summary["pool"],
            summary["paper"],
            summary["opportunity_state"],
            summary["opportunity_reason"],
        )

        return result

    def _run_cycle_sync(self):
        identities = self._watched_identities()

        if not identities:
            self.last_status = self._status(
                state="NO_WATCH_CANDIDATES",
            )
            return self.last_status

        rows = self._cache_rows(identities)

        if not rows:
            self.last_status = self._status(
                state="NO_ACTIVE_WATCH_CANDIDATES",
            )
            return self.last_status

        processed = 0
        failed = 0
        paper_buys = 0

        for row in rows[: self.max_candidates]:
            try:
                result = self._process(row)
                processed += 1

                paper = (
                    result.get("data", {}).get("paper")
                    or {}
                )
                if paper.get("action") == "PAPER_BUY":
                    paper_buys += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Fast watch revisit failed token=%s pool=%s",
                    row.get("token"),
                    row.get("pool"),
                )

        self.last_status = self._status(
            state=(
                "READY"
                if failed == 0
                else "DEGRADED"
            ),
            selected=len(rows),
            processed=processed,
            failed=failed,
            paper_buys=paper_buys,
        )
        return self.last_status

    def _background_cycle(self):
        try:
            self._run_cycle_sync()
        except Exception:
            logger.exception(
                "Fast watch background cycle failed"
            )
            self.last_status = self._status(
                state="DEGRADED",
                failed=1,
            )
        finally:
            with self._state_lock:
                self._running = False

    def run_cycle(self):
        """Dispatch one bounded revisit cycle without blocking Scheduler.tick."""
        with self._state_lock:
            if self._running:
                return self._status(
                    state="BUSY",
                )

            self._running = True
            dispatched = self._status(
                state="DISPATCHED",
            )
            self.last_status = dispatched
            self._thread = threading.Thread(
                target=self._background_cycle,
                name="coinoskobi-fast-watch-revisit",
                daemon=True,
            )
            thread = self._thread

        thread.start()
        return dispatched
