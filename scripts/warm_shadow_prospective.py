import argparse
import json
import math
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.config.settings import WSS_URL
from app.dex.pair_membership import verify_pair_membership
from app.dex.runtime_actor_intelligence import RuntimeActorIntelligence
from app.dex.runtime_market_flow import RuntimeMarketFlowStore
from app.dex.wss_service import NativeWSSService
from app.risk.sellability import analyze as sellability_analyze
from app.risk.stream_stats import calibrate_stream_math
from app.universe.snapshot import DexScreenerSnapshotClient
from scripts.warm_shadow_overnight import (
    BASES,
    MAX_ACTIVE_V2,
    MAX_ACTOR_EVENTS_PER_POOL,
    WINDOWS,
    Collector as BaseCollector,
    Recorder as BaseRecorder,
    epoch,
    utc_now,
)

MEMBERSHIP_WORKERS = 4
SELLABILITY_WORKERS = 2
DEFAULT_POLL_SECONDS = 0.25
COLLECTOR_VERSION = "WARM_PROSPECTIVE_EARLY_FLOW_V1"


def _error_text(exc):
    return f"{type(exc).__name__}: {exc}"[:500]


class ProspectiveRecorder(BaseRecorder):
    def _migrate(self):
        super()._migrate()
        with self.db:
            columns = {
                row[1]
                for row in self.db.execute("PRAGMA table_info(episodes)").fetchall()
            }
            additions = {
                "trigger_buys_m5": "INTEGER",
                "trigger_sells_m5": "INTEGER",
                "trigger_change_m5": "REAL",
                "pretrigger_json": "TEXT",
                "membership_completed_at": "TEXT",
                "sellability_completed_at": "TEXT",
                "wss_eligible_at": "TEXT",
                "wss_requested_at": "TEXT",
                "first_native_at": "TEXT",
                "collector_version": "TEXT",
            }
            for name, sql_type in additions.items():
                if name not in columns:
                    self.db.execute(
                        f"ALTER TABLE episodes ADD COLUMN {name} {sql_type}"
                    )
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS collector_errors(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observed_at TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    error_class TEXT NOT NULL,
                    error_text TEXT NOT NULL
                )
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_collector_errors_time
                ON collector_errors(observed_at)
            """)

    def record_trigger_features(self, episode_id, observation, history):
        history_rows = [dict(row) for row in (history or [])]
        with self.lock, self.db:
            self.db.execute("""
                UPDATE episodes
                SET trigger_buys_m5=?,
                    trigger_sells_m5=?,
                    trigger_change_m5=?,
                    pretrigger_json=?,
                    collector_version=?
                WHERE id=?
            """, (
                observation.get("buys_m5"),
                observation.get("sells_m5"),
                observation.get("change_m5"),
                json.dumps(history_rows[-4:], default=str, sort_keys=True),
                COLLECTOR_VERSION,
                int(episode_id),
            ))

    def update_membership(self, episode_id, membership_state, tracking_state):
        completed = utc_now()
        eligible = completed if (
            membership_state == "VERIFIED" and tracking_state == "TRACKED"
        ) else None
        with self.lock, self.db:
            self.db.execute("""
                UPDATE episodes
                SET membership_state=?,
                    tracking_state=?,
                    membership_completed_at=?,
                    wss_eligible_at=COALESCE(wss_eligible_at, ?)
                WHERE id=?
            """, (
                membership_state,
                tracking_state,
                completed,
                eligible,
                int(episode_id),
            ))

    def update_sellability(self, episode_id, sellability):
        with self.lock, self.db:
            self.db.execute("""
                UPDATE episodes
                SET sellability_json=?,
                    sellability_completed_at=?
                WHERE id=?
            """, (
                json.dumps(sellability, default=str, sort_keys=True),
                utc_now(),
                int(episode_id),
            ))

    def mark_wss_requested(self, episode_ids):
        ids = sorted({int(value) for value in episode_ids})
        if not ids:
            return
        requested_at = utc_now()
        with self.lock, self.db:
            self.db.executemany("""
                UPDATE episodes
                SET wss_requested_at=COALESCE(wss_requested_at, ?)
                WHERE id=?
            """, ((requested_at, episode_id) for episode_id in ids))

    def record_error(self, phase, exc):
        with self.lock, self.db:
            self.db.execute("""
                INSERT INTO collector_errors(
                    observed_at,phase,error_class,error_text
                ) VALUES(?,?,?,?)
            """, (
                utc_now(),
                str(phase),
                type(exc).__name__,
                _error_text(exc),
            ))

    def record_native(self, event, direction, wallet_id=None):
        pool = str(event.get("address") or "").lower()
        episode_id = self.episode_for_pool(pool) if pool else None
        super().record_native(event, direction, wallet_id)
        if episode_id is None:
            return
        with self.lock, self.db:
            self.db.execute("""
                UPDATE episodes
                SET first_native_at=COALESCE(first_native_at, ?)
                WHERE id=?
            """, (utc_now(), int(episode_id)))


class ProspectiveCollector(BaseCollector):
    def __init__(self, cache_db, output_db):
        self.cache = sqlite3.connect(
            f"file:{cache_db}?mode=ro", uri=True, timeout=10
        )
        self.cache.row_factory = sqlite3.Row
        self.rec = ProspectiveRecorder(output_db)
        self.snapshots = DexScreenerSnapshotClient(timeout=5)
        self.flow = RuntimeMarketFlowStore(
            max_pairs=MAX_ACTIVE_V2, max_events_per_pair=2048
        )
        self.actors = RuntimeActorIntelligence(
            chain="bsc", max_pairs=MAX_ACTIVE_V2, max_events_per_pair=2048
        )
        self.wss = None
        self.wss_pairs = []
        self.actor_event_counts = {}
        self.enrichment_pool = ThreadPoolExecutor(
            max_workers=MEMBERSHIP_WORKERS,
            thread_name_prefix="warm-shadow-membership",
        )
        self.sellability_pool = ThreadPoolExecutor(
            max_workers=SELLABILITY_WORKERS,
            thread_name_prefix="warm-shadow-sellability",
        )
        self.enrichment_futures = set()
        self.sellability_futures = set()
        self._future_lock = threading.Lock()

    @staticmethod
    def token_quote(row):
        token0 = str(row.get("token0") or "").lower()
        token1 = str(row.get("token1") or "").lower()
        token0_base = token0 in BASES
        token1_base = token1 in BASES
        if token0_base == token1_base:
            return None, None
        return (token1, token0) if token0_base else (token0, token1)

    def _track_future(self, bucket, future):
        with self._future_lock:
            bucket.add(future)

        def done(item):
            with self._future_lock:
                bucket.discard(item)

        future.add_done_callback(done)

    def _sellability_episode(self, episode_id, pool, token):
        try:
            result = sellability_analyze(token, pair=pool)
        except Exception as exc:
            result = {
                "success": False,
                "error": _error_text(exc),
            }
        self.rec.update_sellability(episode_id, result)

    def _enrich_episode(self, episode_id, dex, pool, token, quote):
        membership = "NOT_APPLICABLE"
        tracking = "TRACKED"

        if dex == "pancakeswap_v2":
            membership = verify_pair_membership(pool, token, quote).get(
                "state", "UNKNOWN"
            )
            if membership != "VERIFIED":
                tracking = "MEMBERSHIP_NOT_VERIFIED"

        self.rec.update_membership(
            episode_id,
            membership_state=membership,
            tracking_state=tracking,
        )

        future = self.sellability_pool.submit(
            self._sellability_episode,
            episode_id,
            pool,
            token,
        )
        self._track_future(self.sellability_futures, future)

    def process_transitions(self):
        last_id = self.rec.get_meta_int("last_eval_id", 0)
        rows = self.cache.execute("""
            SELECT e.*,r.token0,r.token1
            FROM universe_seismic_evaluation_v1 AS e
            JOIN universe_pool_registry AS r
              ON r.chain=e.chain AND r.dex=e.dex AND r.pool=e.pool
            WHERE e.id>?
              AND e.previous_state<>e.next_state
              AND e.next_state IN ('WARM','HOT')
            ORDER BY e.id
        """, (last_id,)).fetchall()

        for raw in rows:
            item = dict(raw)
            token, quote = self.token_quote(item)
            observation = self.latest_observation(
                item["chain"], item["dex"], item["pool"], item["observed_at"]
            )
            observation = dict(observation) if observation else {}
            history = self.history(
                item["chain"], item["dex"], item["pool"], item["observed_at"]
            )
            calibration = (
                calibrate_stream_math(history)
                if history
                else {"state": "INSUFFICIENT_DATA"}
            )
            tracking = "ENRICHING" if token and quote else "NO_SINGLE_BASE"
            episode_id = self.rec.add_episode({
                "eval_id": item["id"],
                "chain": item["chain"],
                "dex": item["dex"],
                "pool": item["pool"],
                "token": token,
                "quote_token": quote,
                "previous_state": item["previous_state"],
                "trigger_state": item["next_state"],
                "triggered_at": item["observed_at"],
                "trigger_price": observation.get("price_usd"),
                "trigger_liquidity": observation.get("liquidity_usd"),
                "trigger_volume_m5": observation.get("volume_m5_usd"),
                "trigger_txns_m5": observation.get("txns_m5"),
                "price_z": item.get("price_z"),
                "volume_z": item.get("volume_z"),
                "txns_z": item.get("txns_z"),
                "liquidity_ratio": item.get("liquidity_ratio"),
                "membership_state": "PENDING" if token and quote else "NOT_APPLICABLE",
                "sellability": None,
                "stream_calibration": calibration,
                "tracking_state": tracking,
            })
            self.rec.record_trigger_features(episode_id, observation, history)

            if tracking == "ENRICHING":
                future = self.enrichment_pool.submit(
                    self._enrich_episode,
                    episode_id,
                    item["dex"],
                    item["pool"],
                    token,
                    quote,
                )
                self._track_future(self.enrichment_futures, future)

            last_id = max(last_id, int(item["id"]))

        self.rec.set_meta("last_eval_id", last_id)
        return len(rows)

    def process_windows(self):
        try:
            return super().process_windows()
        except Exception as exc:
            self.rec.record_error("SNAPSHOT_WINDOWS", exc)
            return 0

    def refresh_wss(self):
        state = super().refresh_wss()
        if not WSS_URL:
            return state
        active = self.rec.active_v2_pools()
        requested_ids = [
            row["id"]
            for row in active
            if row["pool"] in self.wss_pairs
        ]
        self.rec.mark_wss_requested(requested_ids)
        return state

    def close(self):
        if self.wss is not None:
            self.wss.stop()
        self.enrichment_pool.shutdown(wait=False, cancel_futures=True)
        self.sellability_pool.shutdown(wait=False, cancel_futures=True)
        self.cache.close()
        self.rec.db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-db", default="data/cache/cache.db")
    parser.add_argument("--output-db", default="data/warm_shadow_prospective.db")
    parser.add_argument("--duration-hours", type=float, default=12.0)
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    args = parser.parse_args()

    collector = ProspectiveCollector(args.cache_db, args.output_db)
    if collector.rec.get_meta_int("last_eval_id", 0) == 0:
        row = collector.cache.execute(
            "SELECT COALESCE(MAX(id),0) FROM universe_seismic_evaluation_v1"
        ).fetchone()
        collector.rec.set_meta("last_eval_id", int(row[0] if row else 0))

    collector.rec.set_meta("started_at", utc_now())
    collector.rec.set_meta("authority", "OBSERVATION_ONLY")
    collector.rec.set_meta("collector_version", COLLECTOR_VERSION)
    collector.rec.set_meta("windows", ",".join(str(x) for x in WINDOWS))
    collector.rec.set_meta("membership_workers", MEMBERSHIP_WORKERS)
    collector.rec.set_meta("sellability_workers", SELLABILITY_WORKERS)

    deadline = time.monotonic() + max(0.01, args.duration_hours) * 3600.0
    poll = max(0.10, float(args.poll_seconds))

    print("WARM_PROSPECTIVE_STARTED", flush=True)
    print(f"OUTPUT_DB={args.output_db}", flush=True)
    print(f"COLLECTOR_VERSION={COLLECTOR_VERSION}", flush=True)
    print("AUTHORITY=OBSERVATION_ONLY", flush=True)

    try:
        while time.monotonic() < deadline:
            try:
                transitions = collector.process_transitions()
            except Exception as exc:
                collector.rec.record_error("TRANSITIONS", exc)
                transitions = 0

            windows = collector.process_windows()

            try:
                wss_state = collector.refresh_wss()
            except Exception as exc:
                collector.rec.record_error("WSS_REFRESH", exc)
                wss_state = "ERROR"

            if transitions or windows or wss_state == "ERROR":
                print(
                    f"tick transitions={transitions} windows={windows} wss={wss_state}",
                    flush=True,
                )

            time.sleep(poll)
    finally:
        collector.rec.set_meta("stopped_at", utc_now())
        collector.close()
        print("WARM_PROSPECTIVE_STOPPED", flush=True)


if __name__ == "__main__":
    main()
