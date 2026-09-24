#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
DB="$ROOT/data/meta/identity/registry.sqlite3"
META="$ROOT/state/phase0a_transition_universe.json"
PROBE="$ROOT/state/phase0a_transition_kline_probe.json"
APP="$ROOT/app/backfill_transition_klines.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/state/registry.sqlite3.pre_transition_registry.$TS.bak"

cp -a "$DB" "$BACKUP"

"$PY" - "$DB" "$META" "$PROBE" <<'PY'
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

db = Path(sys.argv[1])
meta_path = Path(sys.argv[2])
probe_path = Path(sys.argv[3])

meta = json.loads(meta_path.read_text())
probe = json.loads(probe_path.read_text())
probe_by = {r["old_symbol"]: r for r in probe.get("results", [])}

def did(prefix, *parts):
    raw = "|".join(str(x).strip().upper() for x in parts)
    return f"{prefix}-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

def tr_ms(s):
    if not s:
        return None
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(
        tzinfo=timezone(timedelta(hours=3))
    )
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)

now = time.time_ns() // 1_000_000
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
con.execute("PRAGMA foreign_keys=ON")

before_assets = con.execute("SELECT COUNT(*) FROM asset_registry").fetchone()[0]
before_markets = con.execute("SELECT COUNT(*) FROM market_registry").fetchone()[0]
before_members = con.execute("SELECT COUNT(*) FROM universe_snapshot_members").fetchone()[0]

con.executescript("""
CREATE TABLE IF NOT EXISTS asset_transition_registry (
    transition_id TEXT PRIMARY KEY,
    venue TEXT NOT NULL,
    old_symbol TEXT NOT NULL,
    new_symbol TEXT NOT NULL,
    transition_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    result TEXT NOT NULL,
    swap_ratio_text TEXT,
    economic_continuity TEXT NOT NULL,
    price_series_continuity TEXT NOT NULL,
    trading_end_ms INTEGER,
    new_trading_start_ms INTEGER,
    historical_klines_accessible INTEGER NOT NULL,
    current_same_old_symbol INTEGER NOT NULL,
    evidence_source TEXT NOT NULL,
    evidence_url TEXT NOT NULL,
    evidence_status TEXT NOT NULL,
    recorded_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_asset_transition_symbols
ON asset_transition_registry(old_symbol, new_symbol);
""")

defaults = {
    "reason": "Official Binance TR token transition notice verified; deeper project rationale is not inferred when not explicitly evidenced in the canonical seed.",
    "mechanism": "Old TRY market is closed for the announced token transition; conversion/relisting mechanics are retained only where officially verified.",
    "result": "Historical old-symbol market remains part of the point-in-time universe. Asset and price-series continuity must follow the verified transition semantics rather than ticker text alone.",
    "economic_continuity": "UNCERTAIN_REQUIRES_TRANSITION_SEMANTICS",
    "price_series_continuity": "EPISODE_SPLIT_REQUIRED",
}

rows = []
for t in meta.get("transitions", []):
    p = probe_by.get(t["old_symbol"], {})
    tid = did(
        "TRN", "BINANCE_TR", t["old_symbol"], t["new_symbol"],
        t.get("trading_end_local", ""), t.get("transition_type", "")
    )
    vals = {
        "transition_id": tid,
        "venue": "BINANCE_TR",
        "old_symbol": t["old_symbol"],
        "new_symbol": t["new_symbol"],
        "transition_type": t.get("transition_type") or "TOKEN_TRANSITION",
        "reason": t.get("reason") or defaults["reason"],
        "mechanism": t.get("mechanism") or defaults["mechanism"],
        "result": t.get("result") or defaults["result"],
        "swap_ratio_text": t.get("swap_note"),
        "economic_continuity": t.get("economic_continuity") or defaults["economic_continuity"],
        "price_series_continuity": t.get("price_series_continuity") or defaults["price_series_continuity"],
        "trading_end_ms": tr_ms(t.get("trading_end_local")),
        "new_trading_start_ms": tr_ms(t.get("new_trading_start_local")),
        "historical_klines_accessible": int(p.get("status") == "HISTORICAL_KLINES_ACCESSIBLE"),
        "current_same_old_symbol": int(bool(p.get("currently_active_same_symbol"))),
        "evidence_source": t.get("source") or "BINANCE_TR_OFFICIAL",
        "evidence_url": t.get("source_url") or "",
        "evidence_status": "OFFICIAL_SOURCE_VERIFIED",
        "recorded_at_ms": now,
    }
    con.execute("""
    INSERT INTO asset_transition_registry(
        transition_id, venue, old_symbol, new_symbol, transition_type,
        reason, mechanism, result, swap_ratio_text,
        economic_continuity, price_series_continuity,
        trading_end_ms, new_trading_start_ms,
        historical_klines_accessible, current_same_old_symbol,
        evidence_source, evidence_url, evidence_status, recorded_at_ms
    ) VALUES(
        :transition_id,:venue,:old_symbol,:new_symbol,:transition_type,
        :reason,:mechanism,:result,:swap_ratio_text,
        :economic_continuity,:price_series_continuity,
        :trading_end_ms,:new_trading_start_ms,
        :historical_klines_accessible,:current_same_old_symbol,
        :evidence_source,:evidence_url,:evidence_status,:recorded_at_ms
    )
    ON CONFLICT(transition_id) DO UPDATE SET
        reason=excluded.reason,
        mechanism=excluded.mechanism,
        result=excluded.result,
        swap_ratio_text=excluded.swap_ratio_text,
        economic_continuity=excluded.economic_continuity,
        price_series_continuity=excluded.price_series_continuity,
        new_trading_start_ms=excluded.new_trading_start_ms,
        historical_klines_accessible=excluded.historical_klines_accessible,
        current_same_old_symbol=excluded.current_same_old_symbol,
        evidence_status=excluded.evidence_status,
        recorded_at_ms=excluded.recorded_at_ms
    """, vals)
    rows.append(vals)

# Same-ticker STRAX redenomination must be represented as two market episodes.
strax = next((r for r in rows if r["old_symbol"] == "STRAX_TRY"), None)
if strax:
    current = con.execute(
        "SELECT market_id,asset_id FROM market_registry WHERE source='BINANCE_TR' AND symbol='STRAX_TRY'"
    ).fetchone()
    if current is None:
        raise SystemExit("ABORT_STRAX_CURRENT_MARKET_MISSING")

    con.executescript("""
    CREATE TABLE IF NOT EXISTS market_lifecycle_episodes (
        episode_id TEXT PRIMARY KEY,
        registry_market_id TEXT NOT NULL,
        venue TEXT NOT NULL,
        market_type TEXT NOT NULL,
        symbol TEXT NOT NULL,
        episode_ordinal INTEGER NOT NULL,
        canonical_asset_key TEXT NOT NULL,
        registry_asset_id TEXT,
        trading_start_ms INTEGER,
        trading_end_ms INTEGER,
        episode_status TEXT NOT NULL,
        start_boundary_verified INTEGER NOT NULL DEFAULT 0,
        end_boundary_verified INTEGER NOT NULL DEFAULT 0,
        evidence_source TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        evidence_note TEXT NOT NULL,
        recorded_at_ms INTEGER NOT NULL,
        UNIQUE(venue, market_type, symbol, episode_ordinal),
        FOREIGN KEY(registry_market_id) REFERENCES market_registry(market_id),
        FOREIGN KEY(registry_asset_id) REFERENCES asset_registry(asset_id)
    );
    """)

    episodes = [
        {
            "ordinal": 1,
            "start": None,
            "end": strax["trading_end_ms"],
            "status": "HISTORICAL_ENDED",
            "start_ok": 0,
            "end_ok": 1,
            "key": "STRAX_PRE_2024_REDENOMINATION",
            "note": "Old STRAX denomination; 1 old STRAX converts to 10 new STRAX. Raw price continuity across the boundary is forbidden."
        },
        {
            "ordinal": 2,
            "start": strax["new_trading_start_ms"],
            "end": None,
            "status": "ACTIVE",
            "start_ok": 1,
            "end_ok": 0,
            "key": "STRAX_POST_2024_REDENOMINATION",
            "note": "Post-redenomination STRAX market using the same ticker. Episode-aware or denomination-adjusted analysis is required."
        },
    ]
    for e in episodes:
        eid = did("MEP", "BINANCE_TR", "SPOT", "STRAX_TRY", str(e["ordinal"]))
        con.execute("""
        INSERT INTO market_lifecycle_episodes(
            episode_id, registry_market_id, venue, market_type, symbol,
            episode_ordinal, canonical_asset_key, registry_asset_id,
            trading_start_ms, trading_end_ms, episode_status,
            start_boundary_verified, end_boundary_verified,
            evidence_source, evidence_url, evidence_note, recorded_at_ms
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(episode_id) DO UPDATE SET
            canonical_asset_key=excluded.canonical_asset_key,
            trading_start_ms=excluded.trading_start_ms,
            trading_end_ms=excluded.trading_end_ms,
            episode_status=excluded.episode_status,
            evidence_url=excluded.evidence_url,
            evidence_note=excluded.evidence_note,
            recorded_at_ms=excluded.recorded_at_ms
        """, (
            eid, current["market_id"], "BINANCE_TR", "SPOT", "STRAX_TRY",
            e["ordinal"], e["key"], current["asset_id"], e["start"], e["end"],
            e["status"], e["start_ok"], e["end_ok"], "BINANCE_TR_OFFICIAL",
            strax["evidence_url"], e["note"], now
        ))

con.commit()

after_assets = con.execute("SELECT COUNT(*) FROM asset_registry").fetchone()[0]
after_markets = con.execute("SELECT COUNT(*) FROM market_registry").fetchone()[0]
after_members = con.execute("SELECT COUNT(*) FROM universe_snapshot_members").fetchone()[0]
transition_count = con.execute("SELECT COUNT(*) FROM asset_transition_registry").fetchone()[0]
strax_eps = [
    dict(r) for r in con.execute("""
        SELECT symbol,episode_ordinal,canonical_asset_key,trading_start_ms,trading_end_ms,episode_status
        FROM market_lifecycle_episodes
        WHERE symbol='STRAX_TRY'
        ORDER BY episode_ordinal
    """)
]
fk = con.execute("PRAGMA foreign_key_check").fetchall()
con.close()

if (before_assets, before_markets, before_members) != (after_assets, after_markets, after_members):
    raise SystemExit("FAIL_CORE_REGISTRY_COUNTS_CHANGED")
if fk:
    raise SystemExit(f"FAIL_FOREIGN_KEYS:{fk}")
if transition_count < len(meta.get("transitions", [])):
    raise SystemExit(f"FAIL_TRANSITION_COUNT:{transition_count}")

print(json.dumps({
    "status": "PASS",
    "transition_registry_rows": transition_count,
    "verified_seed_rows": len(meta.get("transitions", [])),
    "core_asset_registry_unchanged": True,
    "core_market_registry_unchanged": True,
    "snapshot_members_unchanged": True,
    "foreign_key_check": "PASS",
    "strax_same_ticker_episode_rows": strax_eps,
}, ensure_ascii=False, indent=2))
PY

# Remove stale schema-v1 dependency keys from future transition queue state.
"$PY" - "$APP" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()

needle = '''        state.update({
            "schema_version": 2,
            "status": "WAITING_ON_HISTORICAL_DEPENDENCIES",
'''
repl = '''        state.pop("dependency_status", None)
        state.pop("dependency_jobs_remaining", None)
        state.update({
            "schema_version": 2,
            "status": "WAITING_ON_HISTORICAL_DEPENDENCIES",
'''
if needle in s and 'state.pop("dependency_status", None)' not in s:
    s = s.replace(needle, repl, 1)

p.write_text(s)
PY

"$PY" -m py_compile "$APP"
systemctl start bintrbot-backfill-transition-klines.service

echo
echo '========== TRANSITION REGISTRY =========='
"$PY" - <<'PY'
import sqlite3
db="/root/bintrbot/data/meta/identity/registry.sqlite3"
con=sqlite3.connect(db)
con.row_factory=sqlite3.Row
print("ROWS=",con.execute("SELECT COUNT(*) FROM asset_transition_registry").fetchone()[0])
for r in con.execute("""
SELECT old_symbol,new_symbol,transition_type,swap_ratio_text,
       economic_continuity,price_series_continuity,historical_klines_accessible
FROM asset_transition_registry
ORDER BY old_symbol
"""):
    print(dict(r))
con.close()
PY

echo
echo '========== QUEUE STATE =========='
cat "$ROOT/state/backfill_transition_klines.json"

echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true
systemctl is-active bintrbot-collector.service || true

echo
echo "BACKUP=$BACKUP"
echo "PHASE0A_TRANSITION_REGISTRY=PASS"
