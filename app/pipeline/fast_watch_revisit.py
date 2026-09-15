import json
import logging
import sqlite3
import threading
import time

import requests
from web3 import Web3

from app.analyzer import pair as pair_module
from app.config.scanner import FAST_WATCH_REVISIT_SECONDS
from app.config.strategy import SELLABILITY_CACHE_TTL_SECONDS
from app.pipeline.market_context import build_market_context
from app.risk import sellability as sellability_module
from app.scanner.adapters.source_router import normalize_source_rows
from app.universe.hot_path import BASE_TOKEN_SET
from app.universe.registry import DEFAULT_DB
from app.universe.schema import DEX_PANCAKESWAP_V2


logger = logging.getLogger(__name__)

FAST_WATCH_REASONS = {
    "ACTIVE_PRICE_SERIES_NOT_READY",
    "ACTIVE_MOMENTUM_NOT_POSITIVE",
    "POSITIVE_CONTINUATION_NOT_ESTABLISHED",
}

FAST_WATCH_MAX_CANDIDATES = 30
FAST_WATCH_HISTORY_PAGE_SIZE = 128
FAST_WATCH_HISTORY_ROW_BUDGET = 2048
FAST_WATCH_IDENTITY_OVERSAMPLE = 8
FAST_WATCH_PROVIDER_BATCH_SIZE = 30

# Factory discovery already sees new Pancake V2 pools close to chain time.
# Give only a small number of previously-unanalysed NEW pools access to the
# same canonical ingress/risk/paper path used by fast-watch. This grants no
# decision/live/wallet/execution authority and does not relax any gate.
FAST_DISCOVERY_MAX_CANDIDATES = 8
FAST_DISCOVERY_ROW_BUDGET = 64
FAST_DISCOVERY_BLOCK_WINDOW = 2000
FAST_DISCOVERY_RETRY_SECONDS = 60.0


class FastWatchRevisitJob:
    """Bounded canonical re-evaluation for momentum-only WATCH candidates."""

    def __init__(
        self,
        pipeline,
        *,
        max_candidates=FAST_WATCH_MAX_CANDIDATES,
        interval_seconds=FAST_WATCH_REVISIT_SECONDS,
    ):
        self.pipeline = pipeline
        self.max_candidates = max(1, int(max_candidates))
        self.interval_seconds = float(interval_seconds)
        if self.interval_seconds <= 0:
            raise ValueError("fast watch interval must be positive")
        self._state_lock = threading.Lock()
        self._running = False
        self._thread = None
        self._ticker_thread = None
        self._stop_event = threading.Event()
        self._discovery_retry_after = {}
        self.last_status = self._status(state="IDLE")

    @staticmethod
    def _canonical(value):
        value = str(value or "").strip().lower()
        if value.startswith("bsc_"):
            value = value[4:]
        return value

    def _selection_limit(self):
        return min(
            FAST_WATCH_HISTORY_ROW_BUDGET,
            max(
                self.max_candidates,
                self.max_candidates * FAST_WATCH_IDENTITY_OVERSAMPLE,
            ),
        )

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

    def _has_canonical_trade_history_block(self, token):
        """
        Mirror the canonical one-paper-trade-per-token database invariant.

        PaperDatabase.insert_if_below_open_limit() rejects a token when any
        prior paper row exists, including a closed row. Fast revisit must not
        spend provider/RPC budget on a token the canonical insert path cannot
        admit. This is deliberately stricter than an open-position-only check.
        """
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

    def _eligible_watch_identity(self, item, *, now):
        token = self._canonical(item.get("token"))
        pool = self._canonical(item.get("pool"))

        if not token or not pool:
            return None

        action = str(item.get("decision_action") or "").upper()
        if action != "WATCH":
            return None

        try:
            observed_at = float(item.get("observed_at") or 0.0)
        except (TypeError, ValueError):
            observed_at = 0.0

        if (
            observed_at > 0
            and now - observed_at < FAST_WATCH_REVISIT_SECONDS
        ):
            return None

        if self._has_canonical_trade_history_block(token):
            return None

        try:
            context = json.loads(item.get("context_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

        if str(context.get("strategy") or "").upper() != "PAPER_BUY":
            return None

        if str(context.get("opportunity_reason") or "").upper() not in FAST_WATCH_REASONS:
            return None

        if bool(context.get("hard_block")):
            return None

        market_context = context.get("market_context") or {}

        if not isinstance(market_context, dict):
            return None

        dex = str(
            market_context.get("candidate_dex")
            or ""
        ).strip().lower()

        if not dex:
            return None

        return (token, pool, dex)

    def _durable_watched_identities(self, db, lock):
        """
        Find a bounded overfetch window of current eligible WATCH identities.

        History is scanned newest-first in small keyset pages, but every cycle
        has a hard total row budget. The first row seen for an identity is its
        newest transition, so older WATCH rows cannot override newer states.
        We intentionally overfetch identities here; the final 30-candidate cap
        is applied only after fresh Gecko snapshot + ingress admission.
        """
        selected = []
        seen = set()
        now = time.time()
        cursor = None
        scanned = 0
        target = self._selection_limit()
        page_size = max(
            FAST_WATCH_HISTORY_PAGE_SIZE,
            self.max_candidates * 2,
        )

        while (
            len(selected) < target
            and scanned < FAST_WATCH_HISTORY_ROW_BUDGET
        ):
            query_limit = min(
                page_size,
                FAST_WATCH_HISTORY_ROW_BUDGET - scanned,
            )

            try:
                with lock:
                    if cursor is None:
                        rows = db.execute(
                            """
                            SELECT *
                            FROM candidate_decision_history
                            ORDER BY id DESC
                            LIMIT ?
                            """,
                            (query_limit,),
                        ).fetchall()
                    else:
                        rows = db.execute(
                            """
                            SELECT *
                            FROM candidate_decision_history
                            WHERE id < ?
                            ORDER BY id DESC
                            LIMIT ?
                            """,
                            (cursor, query_limit),
                        ).fetchall()
            except Exception:
                logger.exception(
                    "Fast watch durable paged-decision query failed"
                )
                return []

            if not rows:
                break

            scanned += len(rows)
            cursor = int(rows[-1]["id"])

            for raw in rows:
                item = dict(raw)
                identity = (
                    self._canonical(item.get("token")),
                    self._canonical(item.get("pool")),
                )

                if not identity[0] or not identity[1] or identity in seen:
                    continue

                seen.add(identity)

                eligible = self._eligible_watch_identity(item, now=now)
                if eligible is not None:
                    selected.append(eligible)
                    if len(selected) >= target:
                        break

            if len(rows) < query_limit:
                break

        return selected

    def _watched_identities(self):
        store = getattr(self.pipeline, "counterfactual_store", None)
        db = getattr(store, "_db", None)
        lock = getattr(store, "_lock", None)

        if db is not None and lock is not None:
            return self._durable_watched_identities(db, lock)

        snapshot = getattr(store, "decision_snapshot", None)
        if not callable(snapshot):
            return []

        target = self._selection_limit()
        rows = snapshot(limit=max(target * 2, target)) or []

        selected = []
        seen = set()
        now = time.time()

        for item in rows:
            if len(selected) >= target:
                break

            identity = (
                self._canonical(item.get("token")),
                self._canonical(item.get("pool")),
            )

            if not identity[0] or not identity[1] or identity in seen:
                continue

            seen.add(identity)
            eligible = self._eligible_watch_identity(item, now=now)

            if eligible is not None:
                selected.append(eligible)

        return selected

    def _unseen_universe_identities(self):
        """
        Return a bounded set of recent factory-discovered V2/base-token pools
        that have never entered candidate_decision_history.

        Selection is anchored to the durable NEW-tail checkpoint rather than
        the registry row's discovery_branch. EXISTING discovery may insert the
        same freshly-created pool first, and registry upsert deliberately keeps
        the original branch label.

        Universe discovery is observational only. Exact-pool market data,
        ingress, analyzers, Risk Engine and paper admission still run through
        the existing canonical path before any decision can be produced.
        """
        store = getattr(self.pipeline, "counterfactual_store", None)
        decision_db = getattr(store, "_db", None)
        decision_lock = getattr(store, "_lock", None)

        if decision_db is None or decision_lock is None:
            return []

        now = time.monotonic()

        # Process-local retry suppression keeps inactive/newborn pools from
        # occupying the same bounded discovery slots every 20 seconds.
        self._discovery_retry_after = {
            identity: retry_after
            for identity, retry_after
            in self._discovery_retry_after.items()
            if retry_after > now
        }

        connection = None

        try:
            connection = sqlite3.connect(DEFAULT_DB)
            connection.row_factory = sqlite3.Row

            checkpoint = connection.execute(
                """
                SELECT MAX(last_scanned_block) AS last_scanned_block
                FROM universe_discovery_checkpoint
                WHERE chain='bsc'
                  AND dex=?
                  AND event_kind='PAIR_CREATED'
                  AND discovery_branch='NEW'
                """,
                (DEX_PANCAKESWAP_V2,),
            ).fetchone()

            tail_block = (
                int(checkpoint["last_scanned_block"])
                if checkpoint is not None
                and checkpoint["last_scanned_block"] is not None
                else None
            )

            if tail_block is None:
                return []

            first_block = max(
                0,
                tail_block - FAST_DISCOVERY_BLOCK_WINDOW + 1,
            )

            rows = connection.execute(
                """
                SELECT pool, token0, token1, creation_block
                FROM universe_pool_registry
                WHERE chain='bsc'
                  AND dex=?
                  AND creation_block BETWEEN ? AND ?
                ORDER BY creation_block DESC
                LIMIT ?
                """,
                (
                    DEX_PANCAKESWAP_V2,
                    first_block,
                    tail_block,
                    FAST_DISCOVERY_ROW_BUDGET,
                ),
            ).fetchall()
        except Exception:
            logger.exception(
                "Fast discovery universe query failed"
            )
            return []
        finally:
            if connection is not None:
                connection.close()

        selected = []

        for raw in rows:
            item = dict(raw)

            pool = self._canonical(item.get("pool"))
            token0 = self._canonical(item.get("token0"))
            token1 = self._canonical(item.get("token1"))

            token0_is_base = token0 in BASE_TOKEN_SET
            token1_is_base = token1 in BASE_TOKEN_SET

            if (
                not pool
                or not token0
                or not token1
                or token0_is_base == token1_is_base
            ):
                continue

            token = (
                token1
                if token0_is_base
                else token0
            )
            identity = (token, pool)

            if self._discovery_retry_after.get(identity, 0.0) > now:
                continue

            if self._has_canonical_trade_history_block(token):
                continue

            try:
                with decision_lock:
                    already_seen = decision_db.execute(
                        """
                        SELECT 1
                        FROM candidate_decision_history
                        WHERE lower(token)=?
                          AND lower(pool)=?
                        LIMIT 1
                        """,
                        identity,
                    ).fetchone()
            except Exception:
                logger.exception(
                    "Fast discovery decision-history query failed"
                )
                return []

            if already_seen is not None:
                continue

            selected.append((
                token,
                pool,
                DEX_PANCAKESWAP_V2,
            ))

            if len(selected) >= FAST_DISCOVERY_MAX_CANDIDATES:
                break

        retry_after = now + FAST_DISCOVERY_RETRY_SECONDS

        for identity in selected:
            self._discovery_retry_after[
                identity[:2]
            ] = retry_after

        return selected

    def _fetch_snapshot_batch(self, snapshots, pools):
        """
        Keep one unsupported DEX identity from aborting the whole WATCH batch.

        The canonical market-data boundary remains strict. Failed batches are
        bisected until the unsupported pool is isolated; only that pool is
        skipped. Other ValueError types still propagate.
        """
        pools = list(pools or [])

        if not pools:
            return []

        try:
            return snapshots(
                pools,
                max_pools=min(
                    FAST_WATCH_PROVIDER_BATCH_SIZE,
                    len(pools),
                ),
                persist_followups=False,
            ) or []
        except requests.RequestException as exc:
            # Provider/network availability is not decision evidence.
            # Fail closed for this bounded batch and let a later ticker cycle
            # retry instead of killing the fast-watch worker.
            logger.warning(
                "Fast watch snapshot provider unavailable error=%s pools=%s",
                type(exc).__name__,
                len(pools),
            )
            return []
        except ValueError as exc:
            if str(exc) != "unsupported DEX":
                raise

            if len(pools) == 1:
                logger.warning(
                    "Fast watch skipping unsupported DEX pool=%s",
                    pools[0],
                )
                return []

            midpoint = max(1, len(pools) // 2)

            return (
                self._fetch_snapshot_batch(
                    snapshots,
                    pools[:midpoint],
                )
                + self._fetch_snapshot_batch(
                    snapshots,
                    pools[midpoint:],
                )
            )

    def _fresh_rows(self, identities):
        scanner = getattr(self.pipeline, "scanner", None)
        snapshots = getattr(scanner, "pool_snapshots", None)
        ingress_gate = getattr(self.pipeline, "ingress_gate", None)
        classify_many = getattr(ingress_gate, "classify_many", None)

        if not callable(snapshots) or not callable(classify_many):
            return []

        if not identities:
            return []

        selected = []

        for start in range(0, len(identities), FAST_WATCH_PROVIDER_BATCH_SIZE):
            batch = identities[start:start + FAST_WATCH_PROVIDER_BATCH_SIZE]

            pools = []
            wanted = set()

            for identity in batch:
                token = identity[0]
                pool = identity[1]
                dex = (
                    identity[2]
                    if len(identity) > 2
                    else None
                )

                wanted.add((token, pool))

                if dex:
                    pools.append({
                        "pool": pool,
                        "dex": dex,
                    })
                else:
                    pools.append(pool)

            fresh = self._fetch_snapshot_batch(
                snapshots,
                pools,
            )

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
                    if len(selected) >= self.max_candidates:
                        return selected

        return selected

    def _analysis_pair(self, token):
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
        market_context["candidate_dex"] = row.get("dex")

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
            "opportunity": dict(score.get("opportunity") or {}),
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
        discovery_identities = self._unseen_universe_identities()
        watched_identities = self._watched_identities()

        identities = []
        seen = set()

        # Factory-discovered identities go first so a full WATCH backlog cannot
        # starve first analysis. The overall provider/analyzer cap is unchanged.
        for identity in (
            list(discovery_identities)
            + list(watched_identities)
        ):
            identity_key = (
                identity[0],
                identity[1],
            )

            if identity_key in seen:
                continue

            seen.add(identity_key)
            identities.append(identity)

            if len(identities) >= self.max_candidates:
                break

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

    def _ticker_loop(self):
        while not self._stop_event.wait(self.interval_seconds):
            logger.info(
                "Fast watch ticker dispatch interval=%ss",
                self.interval_seconds,
            )
            self.run_cycle()

    def start(self):
        with self._state_lock:
            if self._stop_event.is_set():
                return False

            ticker = self._ticker_thread
            if ticker is not None and ticker.is_alive():
                return False

            ticker = threading.Thread(
                target=self._ticker_loop,
                name="coinoskobi-fast-watch-ticker",
                daemon=True,
            )
            self._ticker_thread = ticker

        ticker.start()
        return True

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

    def request_stop(self):
        """
        Signal-only stop request.

        Safe for Runner signal handling: stop ticker dispatch immediately,
        but do not join an in-flight worker here. Full shutdown/join remains
        the responsibility of shutdown().
        """
        self._stop_event.set()
        return self._status(state="STOPPING")

    def shutdown(self):
        self._stop_event.set()

        with self._state_lock:
            ticker = self._ticker_thread
            thread = self._thread

        current = threading.current_thread()

        if (
            ticker is not None
            and ticker.is_alive()
            and ticker is not current
        ):
            ticker.join()

        if (
            thread is not None
            and thread.is_alive()
            and thread is not current
        ):
            thread.join()

        with self._state_lock:
            self._ticker_thread = None
            self._running = False
            self.last_status = self._status(state="STOPPED")

        return self.last_status
