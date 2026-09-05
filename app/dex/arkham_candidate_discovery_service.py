from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.dex.arkham_discovery_provider import fetch_discovery_updates
from app.dex.wallet_candidate_discovery import ingest_wallet_candidates
from app.paper.wallet_discovery_evidence_schema import ensure_wallet_discovery_evidence_schema


DEFAULT_INTERVAL_SECONDS = 900.0
DEFAULT_BOOTSTRAP_LOOKBACK_SECONDS = 3600.0
CURSOR_OVERLAP_SECONDS = 30.0
FEEDS = (
    ("ADDRESS_TAG_UPDATES", "ARKHAM_ADDRESS_TAG_UPDATE"),
)


class ArkhamCandidateDiscoveryService:
    """Slow-path Arkham tagged-address discovery; observations never grant success."""

    name = "arkham-candidate-discovery"

    def __init__(
        self,
        db_path: str | Path,
        *,
        fetcher=fetch_discovery_updates,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        bootstrap_lookback_seconds: float = DEFAULT_BOOTSTRAP_LOOKBACK_SECONDS,
    ):
        self.db_path = Path(db_path)
        self.fetcher = fetcher
        self.interval_seconds = max(300.0, float(interval_seconds))
        self.bootstrap_lookback_seconds = max(
            60.0,
            min(float(bootstrap_lookback_seconds), 86400.0),
        )
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.RLock()
        self.last_cycle_at = None
        self.last_error = None
        self.last_result = self._result("NOT_STARTED")

    @staticmethod
    def _result(state: str, **payload: Any) -> dict[str, Any]:
        return {
            "state": state,
            "feeds_requested": 0,
            "feeds_succeeded": 0,
            "provider_failures": 0,
            "candidates_received": 0,
            "candidates_accepted": 0,
            **payload,
            "candidate_state": "OBSERVED",
            "active_feed": "ADDRESS_TAG_UPDATES",
            "generic_address_feed_active": False,
            "read_only_provider": True,
            "success_authority": False,
            "trade_authority": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def _since_for_feed(self, feed: str, now: float) -> float:
        db = self._connect()
        try:
            ensure_wallet_discovery_evidence_schema(db)
            row = db.execute(
                "SELECT last_success_at FROM wallet_discovery_feed_state WHERE feed=?",
                (feed,),
            ).fetchone()
        finally:
            db.close()
        if row is None or row["last_success_at"] is None:
            return max(0.0, now - self.bootstrap_lookback_seconds)
        return max(0.0, float(row["last_success_at"]) - CURSOR_OVERLAP_SECONDS)

    def _record_feed_state(
        self,
        feed: str,
        *,
        attempted_at: float,
        provider_state: str,
        success_at: float | None = None,
        candidate_count: int = 0,
    ) -> None:
        db = self._connect()
        try:
            ensure_wallet_discovery_evidence_schema(db)
            db.execute(
                """
                INSERT INTO wallet_discovery_feed_state(
                    feed,last_attempt_at,last_success_at,last_provider_state,last_candidate_count
                ) VALUES(?,?,?,?,?)
                ON CONFLICT(feed) DO UPDATE SET
                    last_attempt_at=excluded.last_attempt_at,
                    last_success_at=COALESCE(excluded.last_success_at,wallet_discovery_feed_state.last_success_at),
                    last_provider_state=excluded.last_provider_state,
                    last_candidate_count=excluded.last_candidate_count
                """,
                (
                    feed,
                    attempted_at,
                    success_at,
                    provider_state,
                    int(candidate_count),
                ),
            )
            db.commit()
        finally:
            db.close()

    def run_cycle(self) -> dict[str, Any]:
        if not self.db_path.exists():
            result = self._result("DB_MISSING")
            with self._lock:
                self.last_result = result
                self.last_cycle_at = time.time()
            return result

        requested = succeeded = failures = received = accepted = 0
        for feed, source in FEEDS:
            if self._stop_event.is_set():
                break
            requested += 1
            attempt_at = time.time()
            since = self._since_for_feed(feed, attempt_at)
            raw = self.fetcher(feed=feed, since=since)
            result = raw if isinstance(raw, dict) else {}
            if result.get("available") is not True:
                failures += 1
                self._record_feed_state(
                    feed,
                    attempted_at=attempt_at,
                    provider_state=str(result.get("reason") or "UNAVAILABLE"),
                    candidate_count=0,
                )
                continue

            candidates = result.get("candidates")
            candidates = candidates if isinstance(candidates, list) else []
            received += len(candidates)
            ingest = ingest_wallet_candidates(
                self.db_path,
                candidates,
                source=source,
                source_key=feed.lower(),
                provider="ARKHAM",
                observed_at=float(result.get("fetched_at") or attempt_at),
            )
            accepted += int(ingest.get("accepted") or 0)
            success_at = float(result.get("fetched_at") or time.time())
            self._record_feed_state(
                feed,
                attempted_at=attempt_at,
                success_at=success_at,
                provider_state="READY",
                candidate_count=len(candidates),
            )
            succeeded += 1

        if requested == 0 and self._stop_event.is_set():
            state = "STOPPED"
        elif failures == requested and requested:
            state = "PROVIDER_UNAVAILABLE"
        elif failures:
            state = "PARTIAL"
        elif self._stop_event.is_set() and requested < len(FEEDS):
            state = "STOPPED"
        else:
            state = "READY"

        result = self._result(
            state,
            feeds_requested=requested,
            feeds_succeeded=succeeded,
            provider_failures=failures,
            candidates_received=received,
            candidates_accepted=accepted,
        )
        with self._lock:
            self.last_result = result
            self.last_cycle_at = time.time()
            self.last_error = None
        return result

    def _thread_main(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_cycle()
            except Exception as exc:
                with self._lock:
                    self.last_error = f"{type(exc).__name__}: {exc}"
            if self._stop_event.wait(self.interval_seconds):
                break

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._thread_main,
                name="coinoskobi-arkham-candidate-discovery",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join()
        with self._lock:
            if self._thread is thread:
                self._thread = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            running = bool(self._thread is not None and self._thread.is_alive())
            return {
                "name": self.name,
                "state": "RUNNING" if running else "STOPPED",
                "interval_seconds": self.interval_seconds,
                "last_cycle_at": self.last_cycle_at,
                "last_result": dict(self.last_result),
                "last_error": self.last_error,
                "active_feed": "ADDRESS_TAG_UPDATES",
                "generic_address_feed_active": False,
                "success_authority": False,
                "trade_authority": False,
                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "signing_authority": False,
                "execution_authority": False,
            }
