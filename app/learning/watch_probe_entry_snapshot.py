import json
import sqlite3
import threading
import time
from pathlib import Path


class WatchProbeEntrySnapshotStore:
    VERSION = "WATCH_PROBE_ENTRY_V1"

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False,
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA busy_timeout=30000;")
        self._ensure_schema()

    def _ensure_schema(self):
        with self._lock:
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_probe_entry_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    probe_id INTEGER NOT NULL UNIQUE,
                    decision_history_id INTEGER,
                    captured_at REAL NOT NULL,
                    version TEXT NOT NULL,

                    liquidity_usd REAL,
                    volume_usd REAL,
                    volume_turnover REAL,
                    buys REAL,

                    participant_identity_coverage REAL,
                    origin_participation_coverage REAL,
                    flow_coverage REAL,
                    flow_participant_identity_coverage REAL,
                    native_event_count REAL,

                    market_regime TEXT,
                    flow_confirmation TEXT,
                    flow_quality TEXT,
                    flow_divergence TEXT,
                    liquidity_state TEXT,

                    market_evidence_ready INTEGER,
                    participant_evidence_ready INTEGER,

                    stream_math_state TEXT,
                    volatility_state TEXT,
                    ewma_volatility REAL,
                    price_log_return REAL,
                    liquidity_log_change REAL,

                    raw_context_json TEXT NOT NULL
                )
                """
            )

            self._db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_watch_probe_entry_snapshots_decision
                ON watch_probe_entry_snapshots(decision_history_id)
                """
            )

            self._db.commit()

    @staticmethod
    def _dict(v):
        return v if isinstance(v, dict) else {}

    @staticmethod
    def _bool_int(v):
        if v is True:
            return 1
        if v is False:
            return 0
        return None

    @staticmethod
    def _volatility_state(v):
        if v is None:
            return "UNKNOWN"

        try:
            x = float(v)
        except Exception:
            return "UNKNOWN"

        if x == 0.0:
            return "ZERO"

        return "NONZERO"

    def capture(
        self,
        *,
        probe_id,
        decision_history_id,
        context,
        captured_at=None,
    ):
        if not probe_id:
            return {
                "state": "INVALID",
                "stored": False,
            }

        ctx = self._dict(context)
        mc = self._dict(ctx.get("market_context"))
        mi = self._dict(mc.get("market_intelligence"))
        rmf = self._dict(mc.get("runtime_market_flow"))
        fi = self._dict(rmf.get("flow_intelligence"))
        sm = self._dict(rmf.get("stream_math"))
        ewma = self._dict(sm.get("ewma"))

        ri = self._dict(ctx.get("runtime_intelligence"))
        mq = self._dict(ri.get("market_quality"))
        mr = self._dict(ri.get("market_regime"))
        fc = self._dict(ri.get("flow_confirmation"))
        fq = self._dict(ri.get("flow_quality"))
        fd = self._dict(ri.get("flow_divergence"))

        captured = (
            float(captured_at)
            if captured_at is not None
            else time.time()
        )

        ewma_volatility = ewma.get("ewma_volatility")

        payload = (
            int(probe_id),
            (
                int(decision_history_id)
                if decision_history_id is not None
                else None
            ),
            captured,
            self.VERSION,

            mc.get("liquidity_usd"),
            mi.get("volume_usd"),
            mq.get("volume_turnover"),
            mi.get("buys"),

            mi.get("participant_identity_coverage"),
            self._dict(
                mc.get("origin_participation")
            ).get("coverage"),
            fi.get("coverage"),
            fi.get("participant_identity_coverage"),
            rmf.get("native_event_count"),

            mr.get("market_regime"),
            fc.get("confirmation"),
            fq.get("flow_quality"),
            fd.get("divergence_state"),
            mq.get("liquidity_state"),

            self._bool_int(
                mq.get("market_evidence_ready")
            ),
            self._bool_int(
                mq.get("participant_evidence_ready")
            ),

            sm.get("state"),
            self._volatility_state(
                ewma_volatility
            ),
            ewma_volatility,
            sm.get("price_log_return"),
            sm.get("liquidity_log_change"),

            json.dumps(
                ctx,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

        with self._lock:
            try:
                self._db.execute(
                    """
                    INSERT INTO watch_probe_entry_snapshots(
                        probe_id,
                        decision_history_id,
                        captured_at,
                        version,
                        liquidity_usd,
                        volume_usd,
                        volume_turnover,
                        buys,
                        participant_identity_coverage,
                        origin_participation_coverage,
                        flow_coverage,
                        flow_participant_identity_coverage,
                        native_event_count,
                        market_regime,
                        flow_confirmation,
                        flow_quality,
                        flow_divergence,
                        liquidity_state,
                        market_evidence_ready,
                        participant_evidence_ready,
                        stream_math_state,
                        volatility_state,
                        ewma_volatility,
                        price_log_return,
                        liquidity_log_change,
                        raw_context_json
                    )
                    VALUES(
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?
                    )
                    """,
                    payload,
                )
                self._db.commit()

                return {
                    "state": "CAPTURED",
                    "stored": True,
                }

            except sqlite3.IntegrityError:
                self._db.rollback()

                return {
                    "state": "ALREADY_CAPTURED",
                    "stored": False,
                }

    def snapshot(self, limit=20):
        with self._lock:
            rows = self._db.execute(
                """
                SELECT *
                FROM watch_probe_entry_snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()

        return [dict(r) for r in rows]
