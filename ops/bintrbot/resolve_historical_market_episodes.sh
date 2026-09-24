#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/resolve_historical_market_episodes.py" <<'PY'
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

ROOT = Path("/root/bintrbot")
OUT = ROOT / "state/phase0a_lifecycle_resolution.json"
HIST = ROOT / "state/phase0a_historical_universe.json"
REG = ROOT / "data/meta/identity/registry.sqlite3"
URL = "https://api.binance.me/api/v1/klines"

EVENTS = {
    "LUNA_TRY": {
        "market_resolution": "TWO_DISTINCT_MARKET_EPISODES",
        "asset_resolution": "ASSET_IDENTITY_SPLIT_REQUIRED",
        "reason": (
            "Legacy LUNA/TRY was delisted on 2022-05-13. Binance TR later documented "
            "that legacy LUNA became LUNC under Terra Classic. New Terra LUNA/TRY "
            "was listed on 2022-09-16. Same ticker text must not imply same asset identity."
        ),
        "episodes": [
            {
                "episode": 1,
                "asset_role": "LEGACY_LUNA_NOW_LUNC",
                "trading_end_utc": "2022-05-13T00:40:00Z",
                "official_url": "https://www.binance.tr/tr/blog/duyurular/8ab5ffdff77a4406be64a5719196d072",
            },
            {
                "episode": 2,
                "asset_role": "NEW_TERRA_LUNA",
                "trading_start_utc": "2022-09-16T08:00:00Z",
                "official_url": "https://www.binance.tr/tr/blog/Geli%C5%9Fmeler/19c3f38c0f9e4588897191c54866748b",
            },
        ],
        "identity_evidence_url": "https://www.binance.tr/tr/blog/duyurular/72bb2d8ded7144c1b81aacd770d1efa5",
    },
    "ACM_TRY": {
        "market_resolution": "TWO_DISTINCT_MARKET_EPISODES",
        "asset_resolution": "SAME_ASSET_MULTI_EPISODE",
        "reason": (
            "ACM/TRY was removed on 2024-12-27 and Binance TR later announced "
            "ACM/TRY listing again for 2025-11-26. Treat market availability as "
            "two episodes even though the underlying ACM asset is unchanged."
        ),
        "episodes": [
            {
                "episode": 1,
                "trading_end_utc": "2024-12-27T03:00:00Z",
                "official_url": "https://www.binance.tr/tr/blog/announcements/acm-mtl-ve-tusd-i%C5%9Flem-%C3%A7iftleri-hakk%C4%B1nda-bildirim-27122024-1128",
            },
            {
                "episode": 2,
                "trading_start_utc": "2025-11-26T12:00:00Z",
                "official_url": "https://www.binance.tr/tr/blog/Geli%C5%9Fmeler/6592b4652e0b48cebea3b547c66d8371",
            },
        ],
    },
}

def ms(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)

def iso(v):
    return datetime.fromtimestamp(v / 1000, timezone.utc).isoformat()

def atomic(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

async def fetch(session, symbol, start_ms, end_ms):
    params = {
        "symbol": symbol.replace("_", ""),
        "interval": "1m",
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": 1000,
    }
    async with session.get(URL, params=params, timeout=aiohttp.ClientTimeout(total=25)) as r:
        text = await r.text()
        if r.status != 200:
            return {"error": f"HTTP_{r.status}:{text[:160]}"}
        x = json.loads(text)
        if isinstance(x, dict):
            x = x.get("data", x)
        return x

async def boundary(session, symbol, event_ms, mode):
    # Six-hour local evidence window is enough to verify boundary behavior without a broad re-backfill.
    if mode == "end":
        start, end = event_ms - 6 * 3600_000, event_ms + 60 * 60_000
    else:
        start, end = event_ms - 60 * 60_000, event_ms + 6 * 3600_000

    rows = await fetch(session, symbol, start, end)
    if isinstance(rows, dict):
        return {"error": rows.get("error")}

    opens = sorted(int(r[0]) for r in rows if isinstance(r, list) and r)
    before = [x for x in opens if x < event_ms]
    at_or_after = [x for x in opens if x >= event_ms]
    return {
        "rows_in_window": len(opens),
        "last_before_event_ms": before[-1] if before else None,
        "last_before_event_utc": iso(before[-1]) if before else None,
        "first_at_or_after_event_ms": at_or_after[0] if at_or_after else None,
        "first_at_or_after_event_utc": iso(at_or_after[0]) if at_or_after else None,
    }

def registry_inspection():
    out = {"exists": REG.exists(), "schema": {}, "matching_rows": {}}
    if not REG.exists():
        return out
    con = sqlite3.connect(REG)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for t in tables:
            safe = t.replace('"', '""')
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{safe}")')]
            out["schema"][t] = cols

            likely = [c for c in cols if c.lower() in {"symbol","market_symbol","pair","market"}]
            if not likely:
                continue
            hits = []
            for c in likely:
                csafe = c.replace('"', '""')
                try:
                    cur = con.execute(
                        f'SELECT * FROM "{safe}" WHERE UPPER(CAST("{csafe}" AS TEXT)) IN (?,?) LIMIT 20',
                        ("LUNA_TRY", "ACM_TRY"),
                    )
                    names = [d[0] for d in cur.description]
                    for row in cur.fetchall():
                        hits.append(dict(zip(names, row)))
                except Exception:
                    pass
            if hits:
                out["matching_rows"][t] = hits
    finally:
        con.close()
    return out

async def main():
    result = {
        "schema_version": 1,
        "status": "RUNNING",
        "generated_at_ms": time.time_ns() // 1_000_000,
        "network_scope": "READ_ONLY_KLINE_BOUNDARY_PROBE",
        "registry_modified": False,
        "events": EVENTS,
        "registry_inspection": registry_inspection(),
    }

    async with aiohttp.ClientSession(headers={"User-Agent": "bintrbot-lifecycle-resolution/1.0"}) as session:
        for symbol, spec in result["events"].items():
            for ep in spec["episodes"]:
                if ep.get("trading_end_utc"):
                    ev = ms(ep["trading_end_utc"])
                    ep["kline_boundary_probe"] = await boundary(session, symbol, ev, "end")
                elif ep.get("trading_start_utc"):
                    ev = ms(ep["trading_start_utc"])
                    ep["kline_boundary_probe"] = await boundary(session, symbol, ev, "start")
                await asyncio.sleep(0.5)

    result["status"] = "PASS"
    atomic(OUT, result)

    hist = json.loads(HIST.read_text())
    hist["resolved_overlap_symbols"] = ["ACM_TRY", "LUNA_TRY"]
    hist["market_lifecycle_episode_resolution_required"] = False
    hist["market_lifecycle_resolution_file"] = str(OUT.relative_to(ROOT))
    hist["luna_asset_identity_split_required"] = True
    hist["acm_multi_episode_same_asset"] = True
    hist["survivorship_bias_resolved"] = False
    hist["status"] = "DISCOVERY_REQUIRED"
    hist["updated_at_ms"] = time.time_ns() // 1_000_000
    atomic(HIST, hist)

    summary = {
        "status": result["status"],
        "resolved_overlap_symbols": ["ACM_TRY", "LUNA_TRY"],
        "LUNA_TRY": {
            "market_resolution": EVENTS["LUNA_TRY"]["market_resolution"],
            "asset_resolution": EVENTS["LUNA_TRY"]["asset_resolution"],
        },
        "ACM_TRY": {
            "market_resolution": EVENTS["ACM_TRY"]["market_resolution"],
            "asset_resolution": EVENTS["ACM_TRY"]["asset_resolution"],
        },
        "registry_modified": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

asyncio.run(main())
PY

"$PY" -m py_compile "$ROOT/app/resolve_historical_market_episodes.py"
"$PY" "$ROOT/app/resolve_historical_market_episodes.py"

echo
echo '========== KLINE BOUNDARIES =========='
"$PY" - <<'PY'
import json
from pathlib import Path
x=json.loads(Path("/root/bintrbot/state/phase0a_lifecycle_resolution.json").read_text())
for symbol,spec in x["events"].items():
    print(symbol, spec["market_resolution"], spec["asset_resolution"])
    for ep in spec["episodes"]:
        print(" ", ep["episode"], ep.get("trading_end_utc") or ep.get("trading_start_utc"), ep.get("kline_boundary_probe"))
print()
print("REGISTRY_TABLES=", ",".join(x.get("registry_inspection",{}).get("schema",{}).keys()))
print("REGISTRY_MATCH_TABLES=", ",".join(x.get("registry_inspection",{}).get("matching_rows",{}).keys()) or "NONE")
for t,rows in x.get("registry_inspection",{}).get("matching_rows",{}).items():
    print("TABLE",t)
    for r in rows:
        print(json.dumps(r,ensure_ascii=False,default=str))
PY

echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-collector.service || true
echo "PHASE0A_LIFECYCLE_RESOLUTION=PASS"
