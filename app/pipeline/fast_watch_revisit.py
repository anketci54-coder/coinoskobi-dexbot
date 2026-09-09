import json
import logging
import threading
import time

from web3 import Web3

from app.analyzer import pair as pair_module
from app.config.scanner import FAST_WATCH_REVISIT_SECONDS
from app.config.strategy import SELLABILITY_CACHE_TTL_SECONDS
from app.pipeline.market_context import build_market_context
from app.risk import sellability as sellability_module
from app.scanner.adapters.source_router import normalize_source_rows


logger = logging.getLogger(__name__)

FAST_WATCH_REASONS = {
    "ACTIVE_PRICE_SERIES_NOT_READY",
    "ACTIVE_MOMENTUM_NOT_POSITIVE",
    "POSITIVE_CONTINUATION_NOT_ESTABLISHED",
}

FAST_WATCH_MAX_CANDIDATES = 30


class FastWatchRevisitJob:
    """Bounded canonical re-evaluation for momentum-only WATCH candidates."""

    def __init__(
        self,
        pipeline,
        *,
        max_candidates=FAST_WATCH_MAX_CANDIDATES,
    ):
        self.pipeline = pipeline
        self.max_candidates = max(1, int(max_candidates))
        self._state_lock = threading.Lock()
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self.last_status = self._status(state="IDLE")

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

        direct = getattr(self.pipeline, "paper_db", None)
        if direct is not None:
            databases.append(direct)

        manager = getattr(self.pipeline, "manager", None)
        manager_db = getattr(manager, "db", None)
        if manager_db is not None and manager_db not in databases:
            databases.append(manager_db)

        for database in databases:
            reader = getattr(database, "has_trade_history", None)
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

    def _current_decision_rows(self):
        """Return the latest durable transition for each current WATCH identity."""
        store = getattr(self.pipeline, "counterfactual_store", None)
        db = getattr(store, "_db", None)
        lock = getattr(store, "_lock", None)

        if db is not None and lock is not None:
            try:
                with lock:
                    rows = db.execute(
                        """
                        SELECT d.*
                        FROM candidate_decision_history d
                        JOIN (
                            SELECT token, pool, MAX(id) AS latest_id
                            FROM candidate_decision_history
                            GROUP BY token, pool
                        ) latest
                          ON latest.latest_id = d.id
                        WHERE upper(d.decision_action) = 'WATCH'
                        ORDER BY d.id DESC
                        """
                    ).fetchall()
                return [dict(row) for row in rows]
            except Exception:
                logger.exception(
                    "Fast watch durable latest-decision query failed"
                )
                return []

        snapshot = getattr(store, "decision_snapshot", None)
        if not callable(snapshot):
            return []

        # Test/non-durable fallback only. Production uses the durable latest
        # identity query above, so eligible watches cannot starve behind a
        # fixed global history window.
        return snapshot(
            limit=max(self.max_candidates * 8, self.max_candidates)
        ) or []

    def _watched_identities(self):
        rows = self._current_decision_rows()
        selected = []
        seen = set()
        now = time.time()

        for item in rows:
            if len(selected) >= self.max_candidates:
                break

            token = self._canonical(item.get("token"))
            pool = self._canonical(item.get("pool"))
            identity = (token, pool)

            if not token or not pool or identity in seen:
                continue

            seen.add(identity)

            action = str(item.get("decision_action") or "").upper()
            if action != "WATCH":
                continue

            try:
                observed_at = float(item.get("observed_at") or 0.0)
            except (TypeError, ValueError):
                observed_at = 0.0

            if (
                observed_at > 0
                and now - observed_at < FAST_WATCH_REVISIT_SECONDS
            ):
                continue

            if self._has_trade_history(token):
                continue

            try:
                context = json.loads(item.get("context_json") or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                continue

            if str(context.get("strategy") or "").upper() != "PAPER_BUY":
                continue

            if str(context.get("opportunity_reason") or "").upper() not in FAST_WATCH_REASONS:
                continue

            if bool(context.get("hard_block")):
                continue

            selected.append(identity)

        return selected

    def _fresh_rows(self, identities):
        scanner = getattr(self.pipeline, "scanner", None)
        snapshots = getattr(scanner, "pool_snapshots", None)
        ingress_gate = getattr(self.pipeline, "ingress_gate", None)
        classify_many = getattr(ingress_gate, "classify_many", None)

        # Fail closed: fast revisit must never become an admission bypass.
        if not callable(snapshots) or not callable(classify_many):
            return []

        pools = [pool for _, pool in identities]
        if not pools:
            return []

        fresh = snapshots(
            pools,
            max_pools=self.max_candidates,
            persist_followups=False,
        ) or []

        wanted = set(identities)
        selected = []

        for row in fresh:
            normalized = normalize_source_rows(
                "geckoterminal",
                "bsc",
                [row],
            )
            candidates = normalized.get("candidates", [])
            if not candidates:
                continue

            candidate = candidates[0].to_dict()
            token = self._canonical(candidate.get("token"))
            pool = self._canonical(candidate.get("pool"))

            if (token, pool) not in wanted:
                continue

            ingress = classify_many([candidate])
            active = ingress.get("active", [])
            if active:
                selected.append(active[0])

        return selected

    def _analysis_pair(self, token):
        """Resolve the exact pair used by PipelineEngine's pair analyzer."""
        try:
            result = pair_module.analyze(token)
        except Exception:
            return None

        data = result.get("data") or {}
        pair = data.get("pair")

        if result.get("success") is not True or not data.get("exists") or not pair:
            return None

        try:
            return Web3.to_checksum_address(pair)
        except Exception:
            return None

    def _refresh_local_sellability_evidence(self, row):
        """
        Refresh local on-chain evidence for the exact pair PipelineEngine uses.

        Provider verdicts retain their canonical TTL. The cache payload update
        is compare-and-swap guarded by the original updated_at so a concurrent
        normal analyzer refresh can never be overwritten by an older verdict.
        """
        try:
            token = Web3.to_checksum_address(row.get("token"))
        except Exception:
            return False

        pair = self._analysis_pair(token)
        if pair is None:
            return False

        cache_key = f"bsc:{token.lower()}:{pair.lower()}"
        cache = getattr(sellability_module, "_cache", None)
        getter = getattr(cache, "get_versioned", None)
        replacer = getattr(cache, "replace_payload_if_version", None)
        local_reader = getattr(sellability_module, "_local_evidence", None)

        if not callable(getter) or not callable(replacer) or not callable(local_reader):
            return False

        try:
            versioned = getter(
                "sellability",
                cache_key,
                ttl_seconds=SELLABILITY_CACHE_TTL_SECONDS,
            )
        except Exception:
            return False

        if versioned is None:
            return False

        try:
            result = json.loads(versioned["payload"])
            expected_updated_at = float(versioned["updated_at"])
        except Exception:
            return False

        if result.get("provider_success") is not True:
            return False

        local = local_reader(token, pair)
        data = dict(result.get("data") or {})
        data["local_evidence"] = local
        result["data"] = data
        result["local_evidence_complete"] = bool(local.get("completed"))

        try:
            return bool(
                replacer(
                    "sellability",
                    cache_key,
                    json.dumps(result, default=str),
                    expected_updated_at,
                )
            )
        except Exception:
            return False

    def _process(self, row):
        runtime_feed = getattr(self.pipeline, "native_market_flow", None)
        confirm_pair = getattr(runtime_feed, "confirm_pair_membership", None)

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
        market_context["candidate_pool"] = row.get("pool")
        market_context["candidate_quote_token"] = row.get("quote_token")

        actor_runtime = getattr(
            self.pipeline,
            "native_actor_intelligence",
            None,
        )

        if actor_runtime is not None:
            actor_snapshot = actor_runtime.snapshot(row.get("pool"))
            if actor_snapshot.get("state") == "READY":
                market_context["wallet_id"] = actor_snapshot["wallet_id"]
                market_context["adversary_key"] = actor_snapshot["adversary_key"]
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
            "opportunity_state": score.get("opportunity_state"),
            "opportunity_reason": score.get("opportunity_reason"),
            "plan_blockers": list(paper.get("plan_blockers") or []),
            "sizing_blockers": list(paper.get("sizing_blockers") or []),
            "sizing_reason": paper.get("sizing_reason"),
            "entry_amount_usdt": paper.get("entry_amount_usdt"),
            "mathematical_plan": paper.get("mathematical_plan"),
            "sizing_diagnostics": dict(paper.get("sizing_diagnostics") or {}),
            "vur_kac_entry_shadow": dict(paper.get("vur_kac_entry_shadow") or {}),
            "hard_block": bool(risk_gate.get("hard_block")),
            "score": score.get("score"),
            "confidence": score.get("confidence"),
            "sellability": analyzer_status.get("sellability", {}).get("status"),
            "market_context": data.get("market_context") or market_context,
            "runtime_intelligence": data.get("runtime_intelligence") or {},
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

            observer(observed_row, summary)

        logger.info(
            "Fast watch revisit token=%s pool=%s paper=%s opportunity=%s opportunity_reason=%s",
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
            self.last_status = self._status(state="NO_WATCH_CANDIDATES")
            return self.last_status

        rows = self._fresh_rows(identities)

        if not rows:
            self.last_status = self._status(state="NO_ACTIVE_WATCH_CANDIDATES")
            return self.last_status

        processed = 0
        failed = 0
        paper_buys = 0

        for row in rows[: self.max_candidates]:
            if self._stop_event.is_set():
                break

            try:
                self._refresh_local_sellability_evidence(row)
                result = self._process(row)
                processed += 1

                paper = result.get("data", {}).get("paper") or {}
                if paper.get("action") == "PAPER_BUY":
                    paper_buys += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Fast watch revisit failed token=%s pool=%s",
                    row.get("token"),
                    row.get("pool"),
                )

        state = "STOPPING" if self._stop_event.is_set() else (
            "READY" if failed == 0 else "DEGRADED"
        )
        self.last_status = self._status(
            state=state,
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
            logger.exception("Fast watch background cycle failed")
            self.last_status = self._status(state="DEGRADED", failed=1)
        finally:
            with self._state_lock:
                self._running = False

    def run_cycle(self):
        """Dispatch one bounded revisit cycle without blocking Scheduler.tick."""
        with self._state_lock:
            if self._stop_event.is_set():
                return self._status(state="STOPPED")

            if self._running:
                return self._status(state="BUSY")

            self._running = True
            dispatched = self._status(state="DISPATCHED")
            self.last_status = dispatched
            self._thread = threading.Thread(
                target=self._background_cycle,
                name="coinoskobi-fast-watch-revisit",
                daemon=True,
            )
            thread = self._thread

        thread.start()
        return dispatched

    def shutdown(self):
        """Stop admitting new rows and finish the in-flight candidate cleanly."""
        self._stop_event.set()

        with self._state_lock:
            thread = self._thread

        if thread is not None and thread.is_alive():
            thread.join()

        with self._state_lock:
            self._running = False
            self.last_status = self._status(state="STOPPED")

        return self.last_status
