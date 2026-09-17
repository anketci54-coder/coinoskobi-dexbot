from collections import OrderedDict
from datetime import datetime, timezone
import time

from app.dex.native_ingestion import SWAP_TOPIC as PANCAKE_V2_SWAP_TOPIC
from app.universe.schema import DEX_PANCAKESWAP_V2, DEX_PANCAKESWAP_V3


# keccak256("Swap(address,address,int256,int256,uint160,uint128,int24,uint128,uint128)")
# PancakeSwap V3 uses two trailing protocol-fee fields, so its topic differs
# from canonical Uniswap V3.
PANCAKE_V3_SWAP_TOPIC = (
    "0x19b47279256b2a23a1665c810c8d55a1758940ee09377d4f8d26497a3577dc83"
)
PANCAKE_ACTIVITY_TOPICS = (
    PANCAKE_V2_SWAP_TOPIC,
    PANCAKE_V3_SWAP_TOPIC,
)


class Web3TopicLogReader:
    """Read chain-wide Pancake swap topics without a per-pool address list."""

    def __init__(self, web3):
        self.web3 = web3

    def __call__(self, *, topics, from_block, to_block):
        return self.web3.eth.get_logs({
            "topics": [list(topics)],
            "fromBlock": int(from_block),
            "toBlock": int(to_block),
        })


class PancakeActivityRadar:
    """Durable, bounded BSC-wide Pancake V2/V3 activity trigger."""

    def __init__(
        self,
        registry,
        log_reader,
        *,
        poll_seconds=5.0,
        max_block_span=64,
        replay_blocks=16,
        priority_batch=30,
        max_pending=4096,
        now_func=None,
        utc_now_func=None,
    ):
        self.registry = registry
        self.log_reader = log_reader
        self.poll_seconds = max(1.0, float(poll_seconds))
        self.max_block_span = max(1, int(max_block_span))
        self.replay_blocks = max(1, int(replay_blocks))
        self.priority_batch = max(1, min(30, int(priority_batch)))
        self.max_pending = max(self.priority_batch, int(max_pending))
        self._now = now_func or time.monotonic
        self._utc_now = utc_now_func or (
            lambda: datetime.now(timezone.utc)
        )
        self._next_poll_at = 0.0
        self._pending = OrderedDict()
        self._unknown_pending = OrderedDict()
        self.provider_calls = 0
        self.matched_events = 0
        self.unknown_events = 0
        self.dropped_pending = 0
        self.dropped_unknown = 0
        self._ensure_state_schema()
        self._last_scanned_block = self._load_cursor()
        self._reload_pending()

    def _db(self):
        """Return the registry SQLite connection when available."""
        return getattr(self.registry, "db", None)

    def _ensure_state_schema(self):
        """Create durable cursor and activity queues in the registry database."""
        db = self._db()
        if db is None:
            return
        db.execute("""
            CREATE TABLE IF NOT EXISTS universe_activity_cursor_v1(
                id INTEGER PRIMARY KEY CHECK(id=1),
                last_scanned_block INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS universe_activity_pending_v1(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('KNOWN','UNKNOWN')),
                pool TEXT NOT NULL,
                queued_at TEXT NOT NULL,
                UNIQUE(kind, pool)
            )
        """)
        db.commit()

    def _load_cursor(self):
        """Restore the last fully durably accepted block."""
        db = self._db()
        if db is None:
            return None
        row = db.execute("""
            SELECT last_scanned_block
            FROM universe_activity_cursor_v1
            WHERE id=1
        """).fetchone()
        if row is None:
            return None
        value = int(row[0])
        return value if value >= 0 else None

    def _reload_pending(self):
        """Reload durable queues without changing their FIFO age."""
        db = self._db()
        if db is None:
            return
        rows = db.execute("""
            SELECT kind, pool
            FROM universe_activity_pending_v1
            ORDER BY seq ASC
        """).fetchall()
        self._pending.clear()
        self._unknown_pending.clear()
        for kind, pool in rows:
            target = self._pending if kind == "KNOWN" else self._unknown_pending
            target[str(pool).lower()] = None

    @staticmethod
    def _address(log):
        """Normalize a log emitter address or reject malformed values."""
        value = str((log or {}).get("address") or "").strip().lower()
        if len(value) != 42 or not value.startswith("0x"):
            return None
        return value

    def _known_pancake_pools(self, addresses):
        """Return addresses currently registered as Pancake V2/V3 pools."""
        addresses = list(dict.fromkeys(addresses))
        if not addresses:
            return set()
        db = self._db()
        if db is None:
            return set()

        known = set()
        for offset in range(0, len(addresses), 300):
            chunk = addresses[offset:offset + 300]
            placeholders = ",".join("?" for _ in chunk)
            rows = db.execute(f"""
                SELECT pool
                FROM universe_pool_registry
                WHERE dex IN (?, ?)
                  AND pool IN ({placeholders})
            """, (
                DEX_PANCAKESWAP_V2,
                DEX_PANCAKESWAP_V3,
                *chunk,
            )).fetchall()
            known.update(str(row[0]).strip().lower() for row in rows)
        return known

    def _enqueue_memory(self, target, values, *, unknown=False):
        """Queue new values without reordering values already waiting."""
        for value in values:
            target.setdefault(value, None)
        while len(target) > self.max_pending:
            target.popitem(last=True)
            if unknown:
                self.dropped_unknown += 1
            else:
                self.dropped_pending += 1

    def _trim_durable_kind(self, db, kind):
        """Bound one durable queue while preserving its oldest FIFO entries."""
        count = int(db.execute(
            "SELECT COUNT(*) FROM universe_activity_pending_v1 WHERE kind=?",
            (kind,),
        ).fetchone()[0])
        overflow = max(0, count - self.max_pending)
        if not overflow:
            return 0
        db.execute("""
            DELETE FROM universe_activity_pending_v1
            WHERE seq IN (
                SELECT seq FROM universe_activity_pending_v1
                WHERE kind=? ORDER BY seq DESC LIMIT ?
            )
        """, (kind, overflow))
        return overflow

    def _persist_scan(self, *, to_block, known, unknown):
        """Persist queued activity and cursor atomically before accepting a scan."""
        db = self._db()
        if db is None:
            self._enqueue_memory(self._pending, known)
            self._enqueue_memory(self._unknown_pending, unknown, unknown=True)
            self._last_scanned_block = int(to_block)
            return

        stamp = self._utc_now().isoformat()
        try:
            db.execute("BEGIN")
            for pool in known:
                db.execute("""
                    INSERT OR IGNORE INTO universe_activity_pending_v1(
                        kind, pool, queued_at
                    ) VALUES('KNOWN', ?, ?)
                """, (pool, stamp))
                db.execute("""
                    DELETE FROM universe_activity_pending_v1
                    WHERE kind='UNKNOWN' AND pool=?
                """, (pool,))
            for pool in unknown:
                db.execute("""
                    INSERT OR IGNORE INTO universe_activity_pending_v1(
                        kind, pool, queued_at
                    ) VALUES('UNKNOWN', ?, ?)
                """, (pool, stamp))
            dropped_known = self._trim_durable_kind(db, "KNOWN")
            dropped_unknown = self._trim_durable_kind(db, "UNKNOWN")
            db.execute("""
                INSERT INTO universe_activity_cursor_v1(
                    id, last_scanned_block, updated_at
                ) VALUES(1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    last_scanned_block=excluded.last_scanned_block,
                    updated_at=excluded.updated_at
            """, (int(to_block), stamp))
            db.commit()
        except Exception:
            db.rollback()
            raise

        self.dropped_pending += dropped_known
        self.dropped_unknown += dropped_unknown
        self._last_scanned_block = int(to_block)
        self._reload_pending()

    def _promote_discovered_unknowns(self):
        """Move newly discovered Pancake emitters into the durable priority queue."""
        if not self._unknown_pending:
            return 0
        addresses = list(self._unknown_pending)
        known = self._known_pancake_pools(addresses)
        if not known:
            return 0

        db = self._db()
        if db is None:
            for address in known:
                self._unknown_pending.pop(address, None)
            self._enqueue_memory(self._pending, known)
            return len(known)

        stamp = self._utc_now().isoformat()
        try:
            db.execute("BEGIN")
            for address in known:
                db.execute("""
                    INSERT OR IGNORE INTO universe_activity_pending_v1(
                        kind, pool, queued_at
                    ) VALUES('KNOWN', ?, ?)
                """, (address, stamp))
                db.execute("""
                    DELETE FROM universe_activity_pending_v1
                    WHERE kind='UNKNOWN' AND pool=?
                """, (address,))
            dropped = self._trim_durable_kind(db, "KNOWN")
            db.commit()
        except Exception:
            db.rollback()
            raise
        self.dropped_pending += dropped
        self._reload_pending()
        return len(known)

    def _peek(self):
        """Return the oldest priority batch without removing durable work."""
        return list(self._pending.keys())[:self.priority_batch]

    def acknowledge(self, pools):
        """Remove only pools whose priority snapshot was successfully observed."""
        normalized = list(dict.fromkeys(
            str(pool or "").strip().lower() for pool in pools or []
            if str(pool or "").strip()
        ))
        if not normalized:
            return 0
        db = self._db()
        if db is None:
            removed = 0
            for pool in normalized:
                if pool in self._pending:
                    self._pending.pop(pool, None)
                    removed += 1
            return removed

        placeholders = ",".join("?" for _ in normalized)
        before = int(db.total_changes)
        db.execute(f"""
            DELETE FROM universe_activity_pending_v1
            WHERE kind='KNOWN' AND pool IN ({placeholders})
        """, tuple(normalized))
        db.commit()
        removed = int(db.total_changes) - before
        self._reload_pending()
        return removed

    def run_once(self, *, finalized_block):
        """Scan confirmed blocks and expose the oldest durable priority batch."""
        finalized_block = max(0, int(finalized_block))
        now = self._now()
        provider_call = False
        scanned_from = None
        scanned_to = None
        event_count = 0
        matched_count = 0
        state = "THROTTLED"
        error_class = None

        promoted_after_discovery = self._promote_discovered_unknowns()

        if now >= self._next_poll_at:
            self._next_poll_at = now + self.poll_seconds
            from_block = (
                max(0, finalized_block - self.replay_blocks + 1)
                if self._last_scanned_block is None
                else self._last_scanned_block + 1
            )
            if from_block <= finalized_block:
                to_block = min(
                    finalized_block,
                    from_block + self.max_block_span - 1,
                )
                scanned_from = from_block
                scanned_to = to_block
                provider_call = True
                self.provider_calls += 1
                try:
                    logs = list(self.log_reader(
                        topics=PANCAKE_ACTIVITY_TOPICS,
                        from_block=from_block,
                        to_block=to_block,
                    ))
                    addresses = [
                        address
                        for log in logs
                        if (address := self._address(log)) is not None
                    ]
                    event_count = len(addresses)
                    unique_addresses = list(dict.fromkeys(addresses))
                    known = self._known_pancake_pools(unique_addresses)
                    unknown = [
                        address for address in unique_addresses
                        if address not in known
                    ]
                    matched_count = sum(
                        1 for address in addresses if address in known
                    )
                    self._persist_scan(
                        to_block=to_block,
                        known=known,
                        unknown=unknown,
                    )
                except Exception as exc:
                    state = "DEGRADED"
                    error_class = type(exc).__name__
                else:
                    self.matched_events += matched_count
                    self.unknown_events += max(0, event_count - matched_count)
                    state = "OBSERVED"
            else:
                state = "CAUGHT_UP"

        priority_pools = self._peek()
        return {
            "state": state,
            "from_block": scanned_from,
            "to_block": scanned_to,
            "events": event_count,
            "matched_events": matched_count,
            "priority_pools": priority_pools,
            "priority_count": len(priority_pools),
            "pending": len(self._pending),
            "unknown_pending": len(self._unknown_pending),
            "promoted_after_discovery": promoted_after_discovery,
            "provider_call": provider_call,
            "provider_calls_total": self.provider_calls,
            "matched_events_total": self.matched_events,
            "unknown_events_total": self.unknown_events,
            "dropped_pending": self.dropped_pending,
            "dropped_unknown": self.dropped_unknown,
            "last_scanned_block": self._last_scanned_block,
            "observed_at": self._utc_now().isoformat(),
            "error_class": error_class,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }


__all__ = [
    "PANCAKE_ACTIVITY_TOPICS",
    "PANCAKE_V3_SWAP_TOPIC",
    "PancakeActivityRadar",
    "Web3TopicLogReader",
]
