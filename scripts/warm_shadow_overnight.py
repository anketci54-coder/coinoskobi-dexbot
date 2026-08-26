import argparse
import json
import math
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config.contracts import BASE_TOKENS
from app.config.settings import WSS_URL
from app.dex.pair_membership import verify_pair_membership
from app.dex.runtime_actor_intelligence import RuntimeActorIntelligence
from app.dex.runtime_market_flow import RuntimeMarketFlowStore
from app.dex.wss_service import NativeWSSService
from app.risk.sellability import analyze as sellability_analyze
from app.risk.stream_stats import calibrate_stream_math
from app.universe.snapshot import DexScreenerSnapshotClient

WINDOWS = (15, 30, 60, 120)
MAX_ACTIVE_V2 = 16
BASES = {str(x).strip().lower() for x in BASE_TOKENS}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def pct(a, b):
    a, b = number(a), number(b)
    if a is None or b is None or a == 0:
        return None
    return (b / a - 1.0) * 100.0


class Recorder:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        with self.db:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS episodes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                eval_id INTEGER NOT NULL UNIQUE,
                chain TEXT NOT NULL,
                dex TEXT NOT NULL,
                pool TEXT NOT NULL,
                token TEXT,
                quote_token TEXT,
                previous_state TEXT NOT NULL,
                trigger_state TEXT NOT NULL,
                triggered_at TEXT NOT NULL,
                trigger_price REAL,
                trigger_liquidity REAL,
                trigger_volume_m5 REAL,
                trigger_txns_m5 REAL,
                price_z REAL,
                volume_z REAL,
                txns_z REAL,
                liquidity_ratio REAL,
                membership_state TEXT,
                sellability_json TEXT,
                stream_calibration_json TEXT,
                tracking_state TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS windows(
                episode_id INTEGER NOT NULL,
                window_seconds INTEGER NOT NULL,
                due_at_epoch REAL NOT NULL,
                observed_at TEXT,
                price_usd REAL,
                liquidity_usd REAL,
                volume_m5_usd REAL,
                txns_m5 INTEGER,
                price_change_pct REAL,
                liquidity_change_pct REAL,
                volume_change_pct REAL,
                txns_change_pct REAL,
                PRIMARY KEY(episode_id, window_seconds)
            );
            CREATE TABLE IF NOT EXISTS native_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id INTEGER,
                pool TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                event_identity TEXT,
                direction TEXT,
                wallet_id TEXT,
                transaction_hash TEXT,
                block_number INTEGER,
                log_index INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_windows_due
                ON windows(observed_at, due_at_epoch);
            CREATE INDEX IF NOT EXISTS idx_native_pool_time
                ON native_events(pool, observed_at);
            """)

    def set_meta(self, key, value):
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    def get_meta_int(self, key, default=0):
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        try:
            return int(row[0]) if row else int(default)
        except (TypeError, ValueError):
            return int(default)

    def add_episode(self, payload):
        with self.lock, self.db:
            cur = self.db.execute("""
                INSERT OR IGNORE INTO episodes(
                    eval_id,chain,dex,pool,token,quote_token,
                    previous_state,trigger_state,triggered_at,
                    trigger_price,trigger_liquidity,trigger_volume_m5,trigger_txns_m5,
                    price_z,volume_z,txns_z,liquidity_ratio,
                    membership_state,sellability_json,stream_calibration_json,
                    tracking_state,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                payload["eval_id"], payload["chain"], payload["dex"], payload["pool"],
                payload.get("token"), payload.get("quote_token"), payload["previous_state"],
                payload["trigger_state"], payload["triggered_at"], payload.get("trigger_price"),
                payload.get("trigger_liquidity"), payload.get("trigger_volume_m5"),
                payload.get("trigger_txns_m5"), payload.get("price_z"), payload.get("volume_z"),
                payload.get("txns_z"), payload.get("liquidity_ratio"), payload.get("membership_state"),
                json.dumps(payload.get("sellability"), default=str, sort_keys=True),
                json.dumps(payload.get("stream_calibration"), default=str, sort_keys=True),
                payload["tracking_state"], utc_now(),
            ))
            if cur.rowcount == 0:
                row = self.db.execute("SELECT id FROM episodes WHERE eval_id=?", (payload["eval_id"],)).fetchone()
                return int(row[0])
            episode_id = int(cur.lastrowid)
            base = time.time()
            for seconds in WINDOWS:
                self.db.execute(
                    "INSERT OR IGNORE INTO windows(episode_id,window_seconds,due_at_epoch) VALUES(?,?,?)",
                    (episode_id, seconds, base + seconds),
                )
            return episode_id

    def due_windows(self, now_epoch):
        with self.lock:
            rows = self.db.execute("""
                SELECT w.episode_id,w.window_seconds,e.chain,e.dex,e.pool,
                       e.trigger_price,e.trigger_liquidity,e.trigger_volume_m5,e.trigger_txns_m5
                FROM windows w JOIN episodes e ON e.id=w.episode_id
                WHERE w.observed_at IS NULL AND w.due_at_epoch<=?
                  AND e.tracking_state='TRACKED'
                ORDER BY w.due_at_epoch,w.episode_id
            """, (float(now_epoch),)).fetchall()
        return [dict(r) for r in rows]

    def record_window(self, row, snapshot):
        with self.lock, self.db:
            self.db.execute("""
                UPDATE windows SET observed_at=?,price_usd=?,liquidity_usd=?,
                    volume_m5_usd=?,txns_m5=?,price_change_pct=?,liquidity_change_pct=?,
                    volume_change_pct=?,txns_change_pct=?
                WHERE episode_id=? AND window_seconds=?
            """, (
                snapshot.get("observed_at"), snapshot.get("price_usd"), snapshot.get("liquidity_usd"),
                snapshot.get("volume_m5_usd"), snapshot.get("txns_m5"),
                pct(row.get("trigger_price"), snapshot.get("price_usd")),
                pct(row.get("trigger_liquidity"), snapshot.get("liquidity_usd")),
                pct(row.get("trigger_volume_m5"), snapshot.get("volume_m5_usd")),
                pct(row.get("trigger_txns_m5"), snapshot.get("txns_m5")),
                row["episode_id"], row["window_seconds"],
            ))

    def active_v2_pools(self):
        cutoff = time.time() - max(WINDOWS) - 30
        with self.lock:
            rows = self.db.execute("""
                SELECT id,pool,token,quote_token,triggered_at
                FROM episodes
                WHERE tracking_state='TRACKED' AND dex='pancakeswap_v2'
                ORDER BY id DESC LIMIT ?
            """, (MAX_ACTIVE_V2,)).fetchall()
        result = []
        for r in rows:
            try:
                epoch = datetime.fromisoformat(r["triggered_at"].replace("Z", "+00:00")).timestamp()
            except Exception:
                continue
            if epoch >= cutoff:
                result.append(dict(r))
        return result

    def episode_for_pool(self, pool):
        with self.lock:
            row = self.db.execute(
                "SELECT id FROM episodes WHERE pool=? ORDER BY id DESC LIMIT 1", (pool.lower(),)
            ).fetchone()
        return int(row[0]) if row else None

    def record_native(self, event, direction, wallet_id=None):
        pool = str(event.get("address") or "").lower()
        if not pool:
            return
        with self.lock, self.db:
            self.db.execute("""
                INSERT INTO native_events(
                    episode_id,pool,observed_at,event_identity,direction,wallet_id,
                    transaction_hash,block_number,log_index
                ) VALUES(?,?,?,?,?,?,?,?,?)
            """, (
                self.episode_for_pool(pool), pool, utc_now(), event.get("event_identity"), direction,
                wallet_id, event.get("transaction_hash"), event.get("block_number"), event.get("log_index"),
            ))


class Collector:
    def __init__(self, cache_db, output_db):
        self.cache = sqlite3.connect(f"file:{cache_db}?mode=ro", uri=True, timeout=10)
        self.cache.row_factory = sqlite3.Row
        self.rec = Recorder(output_db)
        self.snapshots = DexScreenerSnapshotClient(timeout=5)
        self.flow = RuntimeMarketFlowStore(max_pairs=MAX_ACTIVE_V2, max_events_per_pair=2048)
        self.actors = RuntimeActorIntelligence(chain="bsc", max_pairs=MAX_ACTIVE_V2, max_events_per_pair=2048)
        self.wss = None
        self.wss_pairs = []

    def token_quote(self, row):
        t0 = str(row.get("token0") or "").lower()
        t1 = str(row.get("token1") or "").lower()
        b0, b1 = t0 in BASES, t1 in BASES
        if b0 == b1:
            return None, None
        return (t1, t0) if b0 else (t0, t1)

    def latest_observation(self, chain, dex, pool, when):
        return self.cache.execute("""
            SELECT * FROM universe_market_observation_v1
            WHERE chain=? AND dex=? AND pool=? AND observed_at<=?
            ORDER BY observed_at DESC LIMIT 1
        """, (chain, dex, pool, when)).fetchone()

    def history(self, chain, dex, pool, when, limit=65):
        rows = self.cache.execute("""
            SELECT * FROM universe_market_observation_v1
            WHERE chain=? AND dex=? AND pool=? AND observed_at<=?
            ORDER BY observed_at DESC LIMIT ?
        """, (chain, dex, pool, when, int(limit))).fetchall()
        return [dict(r) for r in reversed(rows)]

    def process_transitions(self):
        last_id = self.rec.get_meta_int("last_eval_id", 0)
        rows = self.cache.execute("""
            SELECT e.*,r.token0,r.token1
            FROM universe_seismic_evaluation_v1 e
            JOIN universe_pool_registry r
              ON r.chain=e.chain AND r.dex=e.dex AND r.pool=e.pool
            WHERE e.id>? AND e.previous_state<>e.next_state
              AND e.next_state IN ('WARM','HOT')
            ORDER BY e.id
        """, (last_id,)).fetchall()
        for raw in rows:
            r = dict(raw)
            token, quote = self.token_quote(r)
            obs = self.latest_observation(r["chain"], r["dex"], r["pool"], r["observed_at"])
            obs = dict(obs) if obs else {}
            tracking = "TRACKED" if token and quote else "NO_SINGLE_BASE"
            membership = "NOT_APPLICABLE"
            if tracking == "TRACKED" and r["dex"] == "pancakeswap_v2":
                membership = verify_pair_membership(r["pool"], token, quote).get("state", "UNKNOWN")
                if membership != "VERIFIED":
                    tracking = "MEMBERSHIP_NOT_VERIFIED"
            sellability = None
            if tracking == "TRACKED":
                try:
                    sellability = sellability_analyze(token, pair=r["pool"])
                except Exception as exc:
                    sellability = {"success": False, "error": f"{type(exc).__name__}: {exc}"}
            hist = self.history(r["chain"], r["dex"], r["pool"], r["observed_at"])
            calibration = calibrate_stream_math(hist) if hist else {"state": "INSUFFICIENT_DATA"}
            self.rec.add_episode({
                "eval_id": r["id"], "chain": r["chain"], "dex": r["dex"], "pool": r["pool"],
                "token": token, "quote_token": quote, "previous_state": r["previous_state"],
                "trigger_state": r["next_state"], "triggered_at": r["observed_at"],
                "trigger_price": obs.get("price_usd"), "trigger_liquidity": obs.get("liquidity_usd"),
                "trigger_volume_m5": obs.get("volume_m5_usd"), "trigger_txns_m5": obs.get("txns_m5"),
                "price_z": r.get("price_z"), "volume_z": r.get("volume_z"), "txns_z": r.get("txns_z"),
                "liquidity_ratio": r.get("liquidity_ratio"), "membership_state": membership,
                "sellability": sellability, "stream_calibration": calibration, "tracking_state": tracking,
            })
            last_id = max(last_id, int(r["id"]))
        self.rec.set_meta("last_eval_id", last_id)
        return len(rows)

    def process_windows(self):
        due = self.rec.due_windows(time.time())
        if not due:
            return 0
        by_pool = {}
        for row in due:
            by_pool.setdefault(row["pool"], row)
        requested = [
            {"chain": row["chain"], "dex": row["dex"], "pool": pool}
            for pool, row in list(by_pool.items())[:30]
        ]
        snapshots = self.snapshots.fetch(requested)
        snap_by_pool = {s["pool"]: s for s in snapshots}
        written = 0
        for row in due:
            snap = snap_by_pool.get(row["pool"])
            if snap is None:
                continue
            self.rec.record_window(row, snap)
            written += 1
        return written

    async def on_event(self, event):
        result = self.flow.observe_event(event)
        direction = result.get("direction", "UNKNOWN")
        actor = await self.actors.observe_event(event, direction=direction)
        self.rec.record_native(event, direction, actor.get("wallet_id"))
        return True

    async def on_retraction(self, event):
        self.flow.observe_retraction(event)
        await self.actors.observe_retraction(event)
        return True

    def refresh_wss(self):
        if not WSS_URL:
            return "NO_WSS_URL"
        active = self.rec.active_v2_pools()
        pairs = [r["pool"] for r in active]
        if pairs == self.wss_pairs:
            return "UNCHANGED"
        for r in active:
            self.flow.register_pair(r["pool"], r["token"], r["quote_token"])
        if not pairs:
            if self.wss is not None:
                self.wss.stop()
                self.wss = None
            self.wss_pairs = []
            return "NO_ACTIVE"
        if self.wss is None:
            self.wss = NativeWSSService(
                WSS_URL,
                pairs[0] if len(pairs) == 1 else pairs,
                on_event=self.on_event,
                on_retraction=self.on_retraction,
            )
            self.wss.start()
        else:
            self.wss.replace_pairs(pairs[0] if len(pairs) == 1 else pairs)
        self.wss_pairs = pairs
        return "UPDATED"

    def close(self):
        if self.wss is not None:
            self.wss.stop()
        self.cache.close()
        self.rec.db.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-db", default="data/cache/cache.db")
    ap.add_argument("--output-db", default="data/warm_shadow_overnight.db")
    ap.add_argument("--duration-hours", type=float, default=8.0)
    args = ap.parse_args()
    collector = Collector(args.cache_db, args.output_db)
    collector.rec.set_meta("started_at", utc_now())
    collector.rec.set_meta("authority", "OBSERVATION_ONLY")
    deadline = time.monotonic() + max(0.01, args.duration_hours) * 3600.0
    print("WARM_SHADOW_STARTED", flush=True)
    print(f"OUTPUT_DB={args.output_db}", flush=True)
    print("AUTHORITY=OBSERVATION_ONLY", flush=True)
    try:
        while time.monotonic() < deadline:
            transitions = collector.process_transitions()
            windows = collector.process_windows()
            wss_state = collector.refresh_wss()
            if transitions or windows:
                print(
                    f"tick transitions={transitions} windows={windows} wss={wss_state}",
                    flush=True,
                )
            time.sleep(1.0)
    finally:
        collector.rec.set_meta("stopped_at", utc_now())
        collector.close()
        print("WARM_SHADOW_STOPPED", flush=True)


if __name__ == "__main__":
    main()
