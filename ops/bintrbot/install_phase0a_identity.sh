#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

mkdir -p "$ROOT/app" "$ROOT/data/meta/identity/snapshots" "$ROOT/state"

cat > "$ROOT/app/build_identity_registry.py" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/bintrbot")
SYMBOLS = ROOT / "data/meta/symbols.json"
IDROOT = ROOT / "data/meta/identity"
SNAPDIR = IDROOT / "snapshots"
DB = IDROOT / "registry.sqlite3"
CURRENT = IDROOT / "current_try_core.json"
STATE = ROOT / "state/phase0a_identity.json"

def now_ms() -> int:
    return time.time_ns() // 1_000_000

def iso_utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()

def atomic_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

def digest(prefix: str, *parts: str) -> str:
    raw = "|".join(p.strip().upper() for p in parts)
    return f"{prefix}-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

if not SYMBOLS.exists():
    raise SystemExit(f"missing symbols file: {SYMBOLS}")

raw = json.loads(SYMBOLS.read_text())
if isinstance(raw, dict):
    rows = raw.get("symbols") or raw.get("data") or []
elif isinstance(raw, list):
    rows = raw
else:
    raise SystemExit("unsupported symbols.json shape")

parsed = []
rejected = []

for row in rows:
    if not isinstance(row, dict):
        rejected.append({"row": repr(row), "reason": "NOT_OBJECT"})
        continue

    symbol = str(row.get("symbol") or row.get("s") or "").strip().upper()
    if not symbol:
        rejected.append({"row": row, "reason": "MISSING_SYMBOL"})
        continue

    base = str(row.get("baseAsset") or row.get("base_asset") or row.get("base") or "").strip().upper()
    quote = str(row.get("quoteAsset") or row.get("quote_asset") or row.get("quote") or "").strip().upper()

    if not base or not quote:
        if "_" in symbol:
            pbase, pquote = symbol.rsplit("_", 1)
            base = base or pbase
            quote = quote or pquote

    if quote != "TRY":
        continue

    if not base:
        rejected.append({"symbol": symbol, "reason": "BASE_UNRESOLVED"})
        continue

    source_asset_id = digest("ASTP", "BINANCE_TR", "BASE", base)
    market_id = digest("MKT", "BINANCE_TR", "SPOT", symbol)

    parsed.append({
        "market_id": market_id,
        "symbol": symbol,
        "base_symbol": base,
        "quote_symbol": "TRY",
        "asset_id": source_asset_id,
        "asset_identity_status": "PROVISIONAL_SYMBOL_ONLY",
        "market_status": str(row.get("status") or "ACTIVE").upper(),
        "symbol_type": row.get("type"),
        "source": "BINANCE_TR",
    })

if not parsed:
    raise SystemExit("no TRY markets parsed")

symbols = [x["symbol"] for x in parsed]
market_ids = [x["market_id"] for x in parsed]
if len(symbols) != len(set(symbols)):
    raise SystemExit("duplicate TRY symbols detected")
if len(market_ids) != len(set(market_ids)):
    raise SystemExit("duplicate market IDs detected")

ts = now_ms()
snapshot_id = f"TRYCORE-{ts}"
snap_name = f"TRY_CORE_{datetime.fromtimestamp(ts/1000, timezone.utc).strftime('%Y%m%dT%H%M%S')}_{ts}.json"
snap_path = SNAPDIR / snap_name

IDROOT.mkdir(parents=True, exist_ok=True)
SNAPDIR.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode=WAL")
con.execute("PRAGMA foreign_keys=ON")

con.executescript("""
CREATE TABLE IF NOT EXISTS asset_registry (
    asset_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_base_symbol TEXT NOT NULL,
    identity_status TEXT NOT NULL,
    chain_id TEXT,
    contract_id TEXT,
    first_seen_ms INTEGER NOT NULL,
    last_seen_ms INTEGER NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS market_registry (
    market_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    venue TEXT NOT NULL,
    market_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    quote_symbol TEXT NOT NULL,
    market_status TEXT NOT NULL,
    symbol_type INTEGER,
    first_seen_ms INTEGER NOT NULL,
    last_seen_ms INTEGER NOT NULL,
    FOREIGN KEY(asset_id) REFERENCES asset_registry(asset_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_market_source_symbol
ON market_registry(source, symbol);

CREATE TABLE IF NOT EXISTS universe_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    snapshot_at_ms INTEGER NOT NULL,
    snapshot_at_utc TEXT NOT NULL,
    universe TEXT NOT NULL,
    source TEXT NOT NULL,
    market_count INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    sha256 TEXT
);

CREATE TABLE IF NOT EXISTS universe_snapshot_members (
    snapshot_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    PRIMARY KEY(snapshot_id, market_id),
    FOREIGN KEY(snapshot_id) REFERENCES universe_snapshots(snapshot_id),
    FOREIGN KEY(market_id) REFERENCES market_registry(market_id)
);
""")

for x in parsed:
    con.execute("""
    INSERT INTO asset_registry(
        asset_id, source, source_base_symbol, identity_status,
        chain_id, contract_id, first_seen_ms, last_seen_ms, notes
    ) VALUES(?,?,?,?,NULL,NULL,?,?,?)
    ON CONFLICT(asset_id) DO UPDATE SET
        last_seen_ms=excluded.last_seen_ms
    """, (
        x["asset_id"], x["source"], x["base_symbol"],
        x["asset_identity_status"], ts, ts,
        "Provisional identity derived from Binance TR base symbol; requires chain/contract/economic-continuity resolution before canonical merge."
    ))

    con.execute("""
    INSERT INTO market_registry(
        market_id, source, venue, market_type, symbol, asset_id,
        quote_symbol, market_status, symbol_type, first_seen_ms, last_seen_ms
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(market_id) DO UPDATE SET
        market_status=excluded.market_status,
        symbol_type=excluded.symbol_type,
        last_seen_ms=excluded.last_seen_ms
    """, (
        x["market_id"], x["source"], "BINANCE_TR", "SPOT",
        x["symbol"], x["asset_id"], x["quote_symbol"],
        x["market_status"], x["symbol_type"], ts, ts
    ))

snapshot = {
    "schema_version": 1,
    "snapshot_id": snapshot_id,
    "snapshot_at_ms": ts,
    "snapshot_at_utc": iso_utc(ts),
    "universe": "TR-MARKET/TRY-CORE",
    "source": "BINANCE_TR",
    "source_file": str(SYMBOLS),
    "market_count": len(parsed),
    "identity_policy": {
        "market_id": "STABLE_DETERMINISTIC_BINANCE_TR_SPOT_SYMBOL",
        "asset_id": "PROVISIONAL_SYMBOL_ONLY_UNTIL_CHAIN_CONTRACT_ECONOMIC_IDENTITY_RESOLVED",
        "ticker_is_not_canonical_identity": True,
    },
    "markets": sorted(parsed, key=lambda x: x["symbol"]),
    "rejected_rows": rejected,
}

atomic_json(snap_path, snapshot)
atomic_json(CURRENT, snapshot)

sha = hashlib.sha256(snap_path.read_bytes()).hexdigest()
manifest = {
    "snapshot_id": snapshot_id,
    "file": str(snap_path.relative_to(ROOT)),
    "sha256": sha,
    "market_count": len(parsed),
    "created_at_ms": ts,
}
atomic_json(snap_path.with_suffix(".manifest.json"), manifest)

con.execute("""
INSERT INTO universe_snapshots(
    snapshot_id, snapshot_at_ms, snapshot_at_utc, universe,
    source, market_count, source_file, sha256
) VALUES(?,?,?,?,?,?,?,?)
""", (
    snapshot_id, ts, iso_utc(ts), "TR-MARKET/TRY-CORE",
    "BINANCE_TR", len(parsed), str(SYMBOLS), sha
))

for x in parsed:
    con.execute("""
    INSERT INTO universe_snapshot_members(snapshot_id, market_id, symbol, asset_id)
    VALUES(?,?,?,?)
    """, (snapshot_id, x["market_id"], x["symbol"], x["asset_id"]))

con.commit()

asset_count = con.execute("SELECT COUNT(*) FROM asset_registry").fetchone()[0]
market_count = con.execute("SELECT COUNT(*) FROM market_registry").fetchone()[0]
snapshot_count = con.execute("SELECT COUNT(*) FROM universe_snapshots").fetchone()[0]
provisional_count = con.execute(
    "SELECT COUNT(*) FROM asset_registry WHERE identity_status='PROVISIONAL_SYMBOL_ONLY'"
).fetchone()[0]
con.close()

state = {
    "status": "PASS",
    "phase": "0A",
    "built_at_ms": ts,
    "built_at_utc": iso_utc(ts),
    "snapshot_id": snapshot_id,
    "current_try_markets": len(parsed),
    "registry_assets_total": asset_count,
    "registry_markets_total": market_count,
    "snapshots_total": snapshot_count,
    "provisional_assets": provisional_count,
    "rejected_rows": len(rejected),
    "duplicate_symbols": 0,
    "duplicate_market_ids": 0,
    "notes": [
        "MARKET_ID is stable for the Binance TR spot symbol.",
        "ASSET_ID is provisional until chain/contract/economic identity is resolved.",
        "Current market count is a dated snapshot, not a permanent universe fact."
    ],
}
atomic_json(STATE, state)

print(json.dumps(state, ensure_ascii=False, indent=2))
PY

cat > "$ROOT/identity-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
echo '========== PHASE 0A IDENTITY =========='
cat /root/bintrbot/state/phase0a_identity.json 2>/dev/null || echo 'state missing'
echo
echo '========== CURRENT SNAPSHOT =========='
python3 - <<'PY'
import json
from pathlib import Path
p=Path("/root/bintrbot/data/meta/identity/current_try_core.json")
if not p.exists():
    print("snapshot missing")
    raise SystemExit
x=json.loads(p.read_text())
print("SNAPSHOT_ID=", x.get("snapshot_id"))
print("SNAPSHOT_AT=", x.get("snapshot_at_utc"))
print("TRY_MARKETS=", x.get("market_count"))
print("REJECTED_ROWS=", len(x.get("rejected_rows", [])))
print("FIRST_10=", ", ".join(m["symbol"] for m in x.get("markets", [])[:10]))
PY
echo
echo '========== REGISTRY DB =========='
ls -lh /root/bintrbot/data/meta/identity/registry.sqlite3 2>/dev/null || true
echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
SH

chmod +x "$ROOT/identity-status.sh"
"$PY" "$ROOT/app/build_identity_registry.py"
"$ROOT/identity-status.sh"
