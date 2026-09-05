from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.dex.arkham_provider import (
    MAX_TRACKED_ASSETS_PER_WALLET,
    MAX_TRACKED_WALLETS,
    fetch_balances_for_address,
)
from app.paper.wallet_holdings_schema import ensure_wallet_holdings_schema


DEFAULT_INTERVAL_SECONDS = 300.0
DEFAULT_WALLETS_PER_CYCLE = 4
MAX_WALLETS_PER_CYCLE = 16
MAX_CHANGE_ROWS = 4096


class ArkhamSuccessfulWalletService:
    """Bounded Phase 9 slow-path holdings tracker for qualified wallets.

    Only wallets already qualified as SUCCESSFUL by internal realized-outcome
    evidence are enriched. Arkham never grants qualification or trade authority.
    """

    name = "arkham-successful-wallet-holdings"

    def __init__(
        self,
        db_path: str | Path,
        *,
        intelligence=None,
        fetcher=fetch_balances_for_address,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        wallets_per_cycle: int = DEFAULT_WALLETS_PER_CYCLE,
    ):
        self.db_path = Path(db_path)
        self.intelligence = intelligence
        self.fetcher = fetcher
        self.interval_seconds = max(30.0, float(interval_seconds))
        self.wallets_per_cycle = max(
            1,
            min(int(wallets_per_cycle), MAX_WALLETS_PER_CYCLE),
        )
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.RLock()
        self.last_error = None
        self.last_cycle_at = None
        self.last_result = self._result("NOT_STARTED")

    @staticmethod
    def _result(state: str, **payload: Any) -> dict[str, Any]:
        return {
            "state": state,
            "wallets_requested": 0,
            "wallets_updated": 0,
            "provider_failures": 0,
            "change_events": 0,
            **payload,
            "tracked_wallet_cap": MAX_TRACKED_WALLETS,
            "tracked_asset_cap": MAX_TRACKED_ASSETS_PER_WALLET,
            "read_only_provider": True,
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

    @staticmethod
    def _required_phase9_tables(db: sqlite3.Connection) -> bool:
        existing = {
            str(row[0])
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        return {
            "wallet_discovery_registry",
            "wallet_success_score",
        }.issubset(existing)

    @staticmethod
    def _tracked_cohort_wallet_uids(db: sqlite3.Connection) -> list[str]:
        rows = db.execute(
            """
            SELECT lower(r.wallet_uid) AS wallet_uid
            FROM wallet_discovery_registry AS r
            JOIN wallet_success_score AS s
              ON lower(s.wallet_uid)=lower(r.wallet_uid)
            WHERE UPPER(COALESCE(s.qualification_state,''))='SUCCESSFUL'
              AND UPPER(COALESCE(r.discovery_source,''))='TRANSACTION_FROM_ONLY'
              AND lower(COALESCE(r.chain,''))='bsc'
              AND COALESCE(r.address,'')<>''
            ORDER BY COALESCE(s.calculated_at, 0) DESC,
                     lower(r.wallet_uid) ASC
            LIMIT ?
            """,
            (MAX_TRACKED_WALLETS,),
        ).fetchall()
        return [str(row["wallet_uid"]) for row in rows]

    @staticmethod
    def _qualified_wallets(
        db: sqlite3.Connection,
        limit: int,
    ) -> list[dict[str, str]]:
        rows = db.execute(
            """
            WITH tracked_cohort AS (
                SELECT
                    lower(r.wallet_uid) AS wallet_uid,
                    lower(r.chain) AS chain,
                    lower(r.address) AS address,
                    COALESCE(s.calculated_at, 0) AS calculated_at
                FROM wallet_discovery_registry AS r
                JOIN wallet_success_score AS s
                  ON lower(s.wallet_uid)=lower(r.wallet_uid)
                WHERE UPPER(COALESCE(s.qualification_state,''))='SUCCESSFUL'
                  AND UPPER(COALESCE(r.discovery_source,''))='TRANSACTION_FROM_ONLY'
                  AND lower(COALESCE(r.chain,''))='bsc'
                  AND COALESCE(r.address,'')<>''
                ORDER BY COALESCE(s.calculated_at, 0) DESC,
                         lower(r.wallet_uid) ASC
                LIMIT ?
            )
            SELECT
                c.wallet_uid,
                c.chain,
                c.address
            FROM tracked_cohort AS c
            LEFT JOIN wallet_holding_scan_state AS h
              ON lower(h.wallet_uid)=lower(c.wallet_uid)
            ORDER BY COALESCE(h.last_scan_at, 0) ASC,
                     c.calculated_at DESC,
                     c.wallet_uid ASC
            LIMIT ?
            """,
            (
                MAX_TRACKED_WALLETS,
                max(1, min(int(limit), MAX_WALLETS_PER_CYCLE)),
            ),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _prune_outside_cohort(
        db: sqlite3.Connection,
        cohort_wallet_uids: list[str],
    ) -> None:
        cohort = [str(uid).strip().lower() for uid in cohort_wallet_uids if uid]
        if not cohort:
            db.execute("DELETE FROM wallet_holding_snapshot")
            db.execute("DELETE FROM wallet_holding_scan_state")
            return

        placeholders = ",".join("?" for _ in cohort)
        db.execute(
            f"DELETE FROM wallet_holding_snapshot "
            f"WHERE lower(wallet_uid) NOT IN ({placeholders})",
            cohort,
        )
        db.execute(
            f"DELETE FROM wallet_holding_scan_state "
            f"WHERE lower(wallet_uid) NOT IN ({placeholders})",
            cohort,
        )

    @staticmethod
    def _previous_holdings(
        db: sqlite3.Connection,
        wallet_uid: str,
    ) -> dict[str, dict[str, Any]]:
        rows = db.execute(
            """
            SELECT token_id,balance,value_usd
            FROM wallet_holding_snapshot
            WHERE lower(wallet_uid)=lower(?)
            """,
            (wallet_uid,),
        ).fetchall()
        return {str(row["token_id"]): dict(row) for row in rows}

    @staticmethod
    def _balance_changed(previous: float, current: float) -> bool:
        scale = max(1.0, abs(previous), abs(current))
        return abs(previous - current) > scale * 1e-12

    @staticmethod
    def _change_type(previous: float, current: float) -> str:
        if previous <= 0 < current:
            return "ADDED"
        if previous > 0 and current <= 0:
            return "REMOVED"
        return "INCREASED" if current > previous else "DECREASED"

    @staticmethod
    def _trim_changes(db: sqlite3.Connection) -> None:
        db.execute(
            """
            DELETE FROM wallet_holding_change_evidence
            WHERE id NOT IN (
                SELECT id
                FROM wallet_holding_change_evidence
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (MAX_CHANGE_ROWS,),
        )

    @staticmethod
    def _trim_wallet_snapshot(db: sqlite3.Connection, wallet_uid: str) -> None:
        db.execute(
            """
            DELETE FROM wallet_holding_snapshot
            WHERE lower(wallet_uid)=lower(?)
              AND token_id NOT IN (
                  SELECT token_id
                  FROM wallet_holding_snapshot
                  WHERE lower(wallet_uid)=lower(?)
                  ORDER BY observed_at DESC,
                           COALESCE(value_usd, -1.0) DESC,
                           token_id ASC
                  LIMIT ?
              )
            """,
            (
                wallet_uid,
                wallet_uid,
                MAX_TRACKED_ASSETS_PER_WALLET,
            ),
        )

    def _observe_runtime(
        self,
        wallet_uid: str,
        current: dict[str, dict[str, Any]],
        removed: set[str],
        observed_at: float,
    ) -> None:
        observer = getattr(self.intelligence, "observe_wallet_holding", None)
        if not callable(observer):
            return
        for token_id, row in current.items():
            observer(
                wallet_uid,
                token_id,
                row["balance"],
                value_usd=row.get("value_usd"),
                observed_at=observed_at,
            )
        for token_id in removed:
            observer(
                wallet_uid,
                token_id,
                0.0,
                value_usd=0.0,
                observed_at=observed_at,
            )

    def _record_provider_failure(
        self,
        db: sqlite3.Connection,
        wallet_uid: str,
        reason: str,
    ) -> None:
        db.execute(
            """
            INSERT INTO wallet_holding_scan_state(
                wallet_uid,last_scan_at,last_provider_state
            ) VALUES(?,?,?)
            ON CONFLICT(wallet_uid) DO UPDATE SET
                last_scan_at=excluded.last_scan_at,
                last_provider_state=excluded.last_provider_state
            """,
            (wallet_uid, time.time(), reason),
        )

    def _upsert_holding(
        self,
        db: sqlite3.Connection,
        wallet: dict[str, str],
        token_id: str,
        row: dict[str, Any],
        observed_at: float,
    ) -> None:
        db.execute(
            """
            INSERT INTO wallet_holding_snapshot(
                wallet_uid,token_id,chain,address,token_address,pricing_id,
                symbol,name,balance,value_usd,price_usd,price_change_24h_pct,
                observed_at,provider
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(wallet_uid,token_id) DO UPDATE SET
                chain=excluded.chain,
                address=excluded.address,
                token_address=excluded.token_address,
                pricing_id=excluded.pricing_id,
                symbol=excluded.symbol,
                name=excluded.name,
                balance=excluded.balance,
                value_usd=excluded.value_usd,
                price_usd=excluded.price_usd,
                price_change_24h_pct=excluded.price_change_24h_pct,
                observed_at=excluded.observed_at,
                provider=excluded.provider
            """,
            (
                wallet["wallet_uid"],
                token_id,
                wallet["chain"],
                wallet["address"],
                row.get("token_address"),
                row.get("pricing_id"),
                row.get("symbol"),
                row.get("name"),
                row.get("balance"),
                row.get("value_usd"),
                row.get("price_usd"),
                row.get("price_change_24h_pct"),
                observed_at,
                "ARKHAM",
            ),
        )

    def _apply_wallet_snapshot(
        self,
        db: sqlite3.Connection,
        wallet: dict[str, str],
        result: dict[str, Any],
    ) -> int:
        wallet_uid = wallet["wallet_uid"]
        observed_at = float(result.get("fetched_at") or time.time())
        complete_snapshot = result.get("complete_snapshot") is True
        previous = self._previous_holdings(db, wallet_uid)
        current = {
            str(row["token_id"]): dict(row)
            for row in (result.get("holdings") or [])
            if isinstance(row, dict)
            and row.get("token_id")
            and float(row.get("balance") or 0.0) > 0
        }

        comparable_tokens = set(current)
        if complete_snapshot:
            comparable_tokens |= set(previous)

        changes = 0
        for token_id in sorted(comparable_tokens):
            old = previous.get(token_id) or {}
            new = current.get(token_id) or {}
            old_balance = float(old.get("balance") or 0.0)
            new_balance = float(new.get("balance") or 0.0)
            if not self._balance_changed(old_balance, new_balance):
                continue
            db.execute(
                """
                INSERT INTO wallet_holding_change_evidence(
                    wallet_uid,token_id,change_type,
                    previous_balance,current_balance,
                    previous_value_usd,current_value_usd,
                    observed_at,provider
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    wallet_uid,
                    token_id,
                    self._change_type(old_balance, new_balance),
                    old.get("balance"),
                    new.get("balance"),
                    old.get("value_usd"),
                    new.get("value_usd"),
                    observed_at,
                    "ARKHAM",
                ),
            )
            changes += 1

        removed = set(previous) - set(current) if complete_snapshot else set()
        if complete_snapshot:
            db.execute(
                "DELETE FROM wallet_holding_snapshot WHERE lower(wallet_uid)=lower(?)",
                (wallet_uid,),
            )

        for token_id, row in current.items():
            self._upsert_holding(db, wallet, token_id, row, observed_at)

        self._trim_wallet_snapshot(db, wallet_uid)

        provider_state = str(
            result.get("provider_state")
            or ("READY" if complete_snapshot else "PARTIAL_ASSET_CAP")
        )
        asset_count = result.get("available_asset_count")
        if asset_count is None:
            asset_count = len(current)
        db.execute(
            """
            INSERT INTO wallet_holding_scan_state(
                wallet_uid,last_scan_at,last_success_at,last_provider_state,
                total_value_usd,asset_count
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(wallet_uid) DO UPDATE SET
                last_scan_at=excluded.last_scan_at,
                last_success_at=excluded.last_success_at,
                last_provider_state=excluded.last_provider_state,
                total_value_usd=excluded.total_value_usd,
                asset_count=excluded.asset_count
            """,
            (
                wallet_uid,
                observed_at,
                observed_at,
                provider_state,
                result.get("total_value_usd"),
                int(asset_count),
            ),
        )
        self._trim_changes(db)
        self._observe_runtime(
            wallet_uid,
            current,
            removed,
            observed_at,
        )
        return changes

    def run_cycle(self) -> dict[str, Any]:
        if not self.db_path.exists():
            result = self._result("DB_MISSING")
            with self._lock:
                self.last_result = result
                self.last_cycle_at = time.time()
            return result

        db = self._connect()
        requested = updated = failures = changes = 0
        try:
            ensure_wallet_holdings_schema(db)
            if not self._required_phase9_tables(db):
                result = self._result("PHASE9_TABLES_MISSING")
                with self._lock:
                    self.last_result = result
                    self.last_cycle_at = time.time()
                return result

            cohort = self._tracked_cohort_wallet_uids(db)
            self._prune_outside_cohort(db, cohort)
            db.commit()

            wallets = self._qualified_wallets(db, self.wallets_per_cycle)
            requested = len(wallets)
            for wallet in wallets:
                if self._stop_event.is_set():
                    break

                raw_result = self.fetcher(
                    wallet["address"],
                    chain=wallet["chain"],
                )
                result = raw_result if isinstance(raw_result, dict) else {}
                if result.get("available") is not True:
                    failures += 1
                    self._record_provider_failure(
                        db,
                        wallet["wallet_uid"],
                        str(result.get("reason") or "UNAVAILABLE"),
                    )
                    db.commit()
                    continue
                try:
                    changes += self._apply_wallet_snapshot(db, wallet, result)
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                updated += 1
        finally:
            db.close()

        state = "READY"
        if requested == 0:
            state = "NO_SUCCESSFUL_WALLETS"
        elif updated == 0 and failures:
            state = "PROVIDER_UNAVAILABLE"
        elif failures:
            state = "PARTIAL"
        elif self._stop_event.is_set() and updated < requested:
            state = "STOPPED"

        result = self._result(
            state,
            wallets_requested=requested,
            wallets_updated=updated,
            provider_failures=failures,
            change_events=changes,
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
                name="coinoskobi-arkham-successful-wallets",
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
                "wallets_per_cycle": self.wallets_per_cycle,
                "tracked_wallet_cap": MAX_TRACKED_WALLETS,
                "tracked_asset_cap": MAX_TRACKED_ASSETS_PER_WALLET,
                "last_cycle_at": self.last_cycle_at,
                "last_result": dict(self.last_result),
                "last_error": self.last_error,
                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "signing_authority": False,
                "execution_authority": False,
            }
