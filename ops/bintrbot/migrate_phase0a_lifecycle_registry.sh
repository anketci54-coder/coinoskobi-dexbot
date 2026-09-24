#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
DB="$ROOT/data/meta/identity/registry.sqlite3"
STATE="$ROOT/state/phase0a_historical_universe.json"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/state/registry.sqlite3.pre_lifecycle.$TS.bak"

cp -a "$DB" "$BACKUP"

"$PY" - "$DB" "$STATE" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

db = Path(sys.argv[1])
state_path = Path(sys.argv[2])

def epoch(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)

def did(prefix: str, *parts: str) -> str:
    raw = "|".join(str(x).strip().upper() for x in parts)
    return f"{prefix}-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
con.execute("PRAGMA foreign_keys=ON")

before_market_count = con.execute("SELECT COUNT(*) FROM market_registry").fetchone()[0]
before_asset_count = con.execute("SELECT COUNT(*) FROM asset_registry").fetchone()[0]
before_member_count = con.execute("SELECT COUNT(*) FROM universe_snapshot_members").fetchone()[0]

current = {}
for symbol in ("LUNA_TRY", "ACM_TRY"):
    row = con.execute(
        "SELECT market_id, asset_id, symbol FROM market_registry WHERE source='BINANCE_TR' AND symbol=?",
        (symbol,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"ABORT_CURRENT_MARKET_MISSING:{symbol}")
    current[symbol] = dict(row)

lunc = con.execute(
    """
    SELECT asset_id, source_base_symbol
    FROM asset_registry
    WHERE source='BINANCE_TR' AND UPPER(source_base_symbol)='LUNC'
    ORDER BY last_seen_ms DESC
    LIMIT 1
    """
).fetchone()
legacy_lunc_registry_asset_id = lunc["asset_id"] if lunc else None

recorded_at = time.time_ns() // 1_000_000

try:
    con.execute("BEGIN IMMEDIATE")

    con.executescript("""
    CREATE TABLE IF NOT EXISTS asset_lineage (
        lineage_row_id TEXT PRIMARY KEY,
        canonical_asset_key TEXT NOT NULL,
        observed_symbol TEXT NOT NULL,
        registry_asset_id TEXT,
        relation_type TEXT NOT NULL,
        identity_status TEXT NOT NULL,
        evidence_source TEXT NOT NULL,
        evidence_url TEXT NOT NULL,
        evidence_note TEXT NOT NULL,
        recorded_at_ms INTEGER NOT NULL,
        FOREIGN KEY(registry_asset_id) REFERENCES asset_registry(asset_id)
    );

    CREATE INDEX IF NOT EXISTS ix_asset_lineage_canonical_key
    ON asset_lineage(canonical_asset_key);

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

    CREATE INDEX IF NOT EXISTS ix_market_episode_lookup
    ON market_lifecycle_episodes(venue, symbol, trading_start_ms, trading_end_ms);
    """)

    lineage_rows = [
        {
            "canonical_asset_key": "TERRA_CLASSIC_LUNC_LINEAGE",
            "observed_symbol": "LUNA",
            "registry_asset_id": legacy_lunc_registry_asset_id,
            "relation_type": "ORIGINAL_LUNA_RENAMED_TO_LUNC_AFTER_2022_COLLAPSE",
            "identity_status": "RESOLVED_LINEAGE",
            "url": "https://www.binance.tr/tr/blog/duyurular/72bb2d8ded7144c1b81aacd770d1efa5",
            "note": (
                "Pre-collapse original LUNA belongs to the legacy Terra lineage that continued "
                "under ticker LUNC. It must not be stitched to the later Terra 2.0 LUNA asset."
            ),
        },
        {
            "canonical_asset_key": "TERRA_2_LUNA",
            "observed_symbol": "LUNA",
            "registry_asset_id": current["LUNA_TRY"]["asset_id"],
            "relation_type": "NEW_DISTINCT_ASSET_REUSES_LUNA_TICKER",
            "identity_status": "RESOLVED_DISTINCT_ASSET",
            "url": "https://www.binance.tr/tr/blog/Geli%C5%9Fmeler/19c3f38c0f9e4588897191c54866748b",
            "note": (
                "Terra 2.0 LUNA is distinct from the pre-collapse original LUNA/LUNC lineage. "
                "Ticker reuse does not imply asset continuity."
            ),
        },
        {
            "canonical_asset_key": "ACM",
            "observed_symbol": "ACM",
            "registry_asset_id": current["ACM_TRY"]["asset_id"],
            "relation_type": "SAME_ASSET_ACROSS_MULTIPLE_MARKET_EPISODES",
            "identity_status": "RESOLVED_SAME_ASSET",
            "url": "https://www.binance.tr/tr/blog/Geli%C5%9Fmeler/6592b4652e0b48cebea3b547c66d8371",
            "note": (
                "ACM underlying asset is treated as the same asset across separate ACM/TRY "
                "listing episodes; market availability is discontinuous."
            ),
        },
    ]

    for r in lineage_rows:
        rid = did("LIN", r["canonical_asset_key"], r["observed_symbol"], r["relation_type"])
        con.execute(
            """
            INSERT INTO asset_lineage(
                lineage_row_id, canonical_asset_key, observed_symbol, registry_asset_id,
                relation_type, identity_status, evidence_source, evidence_url,
                evidence_note, recorded_at_ms
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(lineage_row_id) DO UPDATE SET
                registry_asset_id=excluded.registry_asset_id,
                identity_status=excluded.identity_status,
                evidence_url=excluded.evidence_url,
                evidence_note=excluded.evidence_note,
                recorded_at_ms=excluded.recorded_at_ms
            """,
            (
                rid, r["canonical_asset_key"], r["observed_symbol"], r["registry_asset_id"],
                r["relation_type"], r["identity_status"], "BINANCE_TR_OFFICIAL",
                r["url"], r["note"], recorded_at,
            ),
        )

    episodes = [
        {
            "symbol": "LUNA_TRY",
            "ordinal": 1,
            "asset_key": "TERRA_CLASSIC_LUNC_LINEAGE",
            "registry_asset_id": legacy_lunc_registry_asset_id,
            "start": None,
            "end": epoch("2022-05-13T00:40:00Z"),
            "status": "HISTORICAL_ENDED",
            "start_ok": 0,
            "end_ok": 1,
            "url": "https://www.binance.tr/tr/blog/duyurular/8ab5ffdff77a4406be64a5719196d072",
            "note": (
                "Legacy LUNA/TRY episode. Kline boundary probe verified last candle at "
                "2022-05-13T00:39:00Z immediately before the 00:40Z trading end."
            ),
        },
        {
            "symbol": "LUNA_TRY",
            "ordinal": 2,
            "asset_key": "TERRA_2_LUNA",
            "registry_asset_id": current["LUNA_TRY"]["asset_id"],
            "start": epoch("2022-09-16T08:00:00Z"),
            "end": None,
            "status": "ACTIVE",
            "start_ok": 1,
            "end_ok": 0,
            "url": "https://www.binance.tr/tr/blog/Geli%C5%9Fmeler/19c3f38c0f9e4588897191c54866748b",
            "note": (
                "New Terra 2.0 LUNA/TRY episode. Kline boundary probe verified first candle "
                "exactly at 2022-09-16T08:00:00Z."
            ),
        },
        {
            "symbol": "ACM_TRY",
            "ordinal": 1,
            "asset_key": "ACM",
            "registry_asset_id": current["ACM_TRY"]["asset_id"],
            "start": None,
            "end": epoch("2024-12-27T03:00:00Z"),
            "status": "HISTORICAL_ENDED",
            "start_ok": 0,
            "end_ok": 1,
            "url": "https://www.binance.tr/tr/blog/announcements/acm-mtl-ve-tusd-i%C5%9Flem-%C3%A7iftleri-hakk%C4%B1nda-bildirim-27122024-1128",
            "note": (
                "First ACM/TRY episode. Kline boundary probe verified last candle at "
                "2024-12-27T02:59:00Z immediately before removal."
            ),
        },
        {
            "symbol": "ACM_TRY",
            "ordinal": 2,
            "asset_key": "ACM",
            "registry_asset_id": current["ACM_TRY"]["asset_id"],
            "start": epoch("2025-11-26T12:00:00Z"),
            "end": None,
            "status": "ACTIVE",
            "start_ok": 1,
            "end_ok": 0,
            "url": "https://www.binance.tr/tr/blog/Geli%C5%9Fmeler/6592b4652e0b48cebea3b547c66d8371",
            "note": (
                "Second ACM/TRY episode. Kline boundary probe verified first candle exactly "
                "at 2025-11-26T12:00:00Z."
            ),
        },
    ]

    for e in episodes:
        mid = current[e["symbol"]]["market_id"]
        eid = did("MEP", "BINANCE_TR", "SPOT", e["symbol"], str(e["ordinal"]))
        con.execute(
            """
            INSERT INTO market_lifecycle_episodes(
                episode_id, registry_market_id, venue, market_type, symbol,
                episode_ordinal, canonical_asset_key, registry_asset_id,
                trading_start_ms, trading_end_ms, episode_status,
                start_boundary_verified, end_boundary_verified,
                evidence_source, evidence_url, evidence_note, recorded_at_ms
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(episode_id) DO UPDATE SET
                canonical_asset_key=excluded.canonical_asset_key,
                registry_asset_id=excluded.registry_asset_id,
                trading_start_ms=excluded.trading_start_ms,
                trading_end_ms=excluded.trading_end_ms,
                episode_status=excluded.episode_status,
                start_boundary_verified=excluded.start_boundary_verified,
                end_boundary_verified=excluded.end_boundary_verified,
                evidence_url=excluded.evidence_url,
                evidence_note=excluded.evidence_note,
                recorded_at_ms=excluded.recorded_at_ms
            """,
            (
                eid, mid, "BINANCE_TR", "SPOT", e["symbol"], e["ordinal"],
                e["asset_key"], e["registry_asset_id"], e["start"], e["end"],
                e["status"], e["start_ok"], e["end_ok"], "BINANCE_TR_OFFICIAL",
                e["url"], e["note"], recorded_at,
            ),
        )

    con.commit()

except Exception:
    con.rollback()
    raise

after_market_count = con.execute("SELECT COUNT(*) FROM market_registry").fetchone()[0]
after_asset_count = con.execute("SELECT COUNT(*) FROM asset_registry").fetchone()[0]
after_member_count = con.execute("SELECT COUNT(*) FROM universe_snapshot_members").fetchone()[0]

episodes_now = [dict(r) for r in con.execute(
    """
    SELECT episode_id,symbol,episode_ordinal,canonical_asset_key,registry_asset_id,
           trading_start_ms,trading_end_ms,episode_status,
           start_boundary_verified,end_boundary_verified
    FROM market_lifecycle_episodes
    WHERE symbol IN ('LUNA_TRY','ACM_TRY')
    ORDER BY symbol,episode_ordinal
    """
)]

lineage_now = [dict(r) for r in con.execute(
    """
    SELECT canonical_asset_key,observed_symbol,registry_asset_id,
           relation_type,identity_status
    FROM asset_lineage
    WHERE canonical_asset_key IN ('TERRA_CLASSIC_LUNC_LINEAGE','TERRA_2_LUNA','ACM')
    ORDER BY canonical_asset_key,relation_type
    """
)]

fk = con.execute("PRAGMA foreign_key_check").fetchall()
con.close()

if before_market_count != after_market_count:
    raise SystemExit(f"FAIL_MARKET_COUNT_CHANGED:{before_market_count}->{after_market_count}")
if before_asset_count != after_asset_count:
    raise SystemExit(f"FAIL_ASSET_COUNT_CHANGED:{before_asset_count}->{after_asset_count}")
if before_member_count != after_member_count:
    raise SystemExit(f"FAIL_SNAPSHOT_MEMBER_COUNT_CHANGED:{before_member_count}->{after_member_count}")
if len(episodes_now) != 4:
    raise SystemExit(f"FAIL_EPISODE_COUNT:{len(episodes_now)}")
if fk:
    raise SystemExit(f"FAIL_FOREIGN_KEYS:{fk}")

st = json.loads(state_path.read_text())
st["lifecycle_identity_status"] = "PASS"
st["market_episode_rows_verified"] = 4
st["luna_identity_rule"] = (
    "PRE_COLLAPSE_LUNA_HISTORY_BELONGS_TO_TERRA_CLASSIC_LUNC_LINEAGE;"
    "NEW_TERRA_2_LUNA_IS_DISTINCT_ASSET"
)
st["acm_identity_rule"] = "SAME_ASSET_TWO_DISTINCT_TRY_MARKET_EPISODES"
st["bronze_rewrite_required"] = False
st["silver_episode_mapping_required"] = True
st["lifecycle_registry_tables"] = ["asset_lineage", "market_lifecycle_episodes"]
st["updated_at_ms"] = recorded_at

tmp = state_path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(st, ensure_ascii=False, indent=2, sort_keys=True))
os.replace(tmp, state_path)

print(json.dumps({
    "status": "PASS",
    "market_registry_unchanged": before_market_count == after_market_count,
    "asset_registry_unchanged": before_asset_count == after_asset_count,
    "snapshot_members_unchanged": before_member_count == after_member_count,
    "foreign_key_check": "PASS",
    "episode_rows": episodes_now,
    "asset_lineage_rows": lineage_now,
    "legacy_lunc_registry_asset_linked": legacy_lunc_registry_asset_id is not None,
    "bronze_rewrite_required": False,
    "silver_episode_mapping_required": True,
}, ensure_ascii=False, indent=2))
PY

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-collector.service || true

echo
echo "BACKUP=$BACKUP"
echo "PHASE0A_LIFECYCLE_REGISTRY_MIGRATION=PASS"
