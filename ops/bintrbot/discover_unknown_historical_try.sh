#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/discover_unknown_historical_try.py" <<'PY'
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import aiohttp

ROOT = Path("/root/bintrbot")
CURRENT = ROOT / "data/meta/symbols.json"
DELISTED = ROOT / "state/phase0a_historical_universe.json"
TRANSITIONS = ROOT / "state/phase0a_transition_universe.json"
OUT = ROOT / "state/phase0a_unknown_historical_try_discovery.json"
CHECKPOINT = ROOT / "state/phase0a_unknown_historical_try_checkpoint.json"

TR_KLINES = "https://api.binance.me/api/v1/klines"
GLOBAL_EXCHANGEINFO = [
    "https://data-api.binance.vision/api/v3/exchangeInfo",
    "https://api.binance.com/api/v3/exchangeInfo",
    "https://api1.binance.com/api/v3/exchangeInfo",
    "https://api2.binance.com/api/v3/exchangeInfo",
    "https://api3.binance.com/api/v3/exchangeInfo",
]
START_MS = 1577836800000  # 2020-01-01T00:00:00Z
REQ_GAP = 0.30

def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def atomic(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

def current_symbols():
    raw = load(CURRENT, {})
    rows = raw.get("symbols") or raw.get("data") or []
    return {
        str(r.get("symbol", "")).upper()
        for r in rows
        if isinstance(r, dict) and r.get("symbol")
    }

def known_historical_symbols():
    d = load(DELISTED, {})
    t = load(TRANSITIONS, {})
    known = {
        str(r.get("symbol", "")).upper()
        for r in d.get("confirmed_delisted_try_seed", [])
        if isinstance(r, dict) and r.get("symbol")
    }
    known |= {
        str(r.get("old_symbol", "")).upper()
        for r in t.get("transitions", [])
        if isinstance(r, dict) and r.get("old_symbol")
    }
    return known

async def fetch_json(session, url, params=None, retries=5):
    last = None
    for n in range(retries):
        try:
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as r:
                text = await r.text()
                if r.status == 200:
                    return json.loads(text), None
                last = f"HTTP_{r.status}:{text[:180]}"
                if r.status in (418, 429) or r.status >= 500:
                    await asyncio.sleep(min(2 ** n, 20))
                    continue
                return None, last
        except Exception as e:
            last = repr(e)
            await asyncio.sleep(min(2 ** n, 20))
    return None, last

async def global_bases(session):
    errors = []
    for url in GLOBAL_EXCHANGEINFO:
        data, err = await fetch_json(session, url)
        if err:
            errors.append({"url": url, "error": err})
            continue
        rows = data.get("symbols", []) if isinstance(data, dict) else []
        bases = sorted({
            str(r.get("baseAsset", "")).upper()
            for r in rows
            if isinstance(r, dict) and r.get("baseAsset")
        })
        if bases:
            return bases, url, errors
    raise RuntimeError(f"GLOBAL_EXCHANGEINFO_UNAVAILABLE:{errors}")

async def probe_try(session, symbol):
    data, err = await fetch_json(
        session,
        TR_KLINES,
        params={
            "symbol": symbol.replace("_", ""),
            "interval": "1m",
            "startTime": START_MS,
            "endTime": int(time.time() * 1000),
            "limit": 1,
        },
        retries=4,
    )
    if err:
        # Invalid / never-listed symbols are normal discovery negatives.
        if "HTTP_400" in err or "HTTP_404" in err:
            return {"status": "NO_HISTORICAL_EVIDENCE", "error": err}
        return {"status": "PROBE_ERROR", "error": err}

    if isinstance(data, dict):
        payload = data.get("data", data)
    else:
        payload = data

    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        return {
            "status": "HISTORICAL_KLINES_ACCESSIBLE",
            "first_open_time_ms": int(payload[0][0]),
            "first_open": str(payload[0][1]),
        }

    return {"status": "NO_HISTORICAL_EVIDENCE", "error": None}

async def main():
    cur = current_symbols()
    known = known_historical_symbols()
    checkpoint = load(CHECKPOINT, {"results": {}})
    results = checkpoint.get("results", {})

    async with aiohttp.ClientSession(
        headers={"User-Agent": "bintrbot-historical-universe-discovery/1.0"}
    ) as session:
        bases, global_source, source_errors = await global_bases(session)

        candidates = sorted({
            f"{base}_TRY"
            for base in bases
            if base and f"{base}_TRY" not in cur and f"{base}_TRY" not in known
        })

        for i, symbol in enumerate(candidates, 1):
            if symbol in results:
                continue
            r = await probe_try(session, symbol)
            results[symbol] = r
            checkpoint = {
                "schema_version": 1,
                "status": "RUNNING",
                "global_candidate_source": global_source,
                "global_base_assets_total": len(bases),
                "candidates_total": len(candidates),
                "checked_total": len(results),
                "updated_at_ms": time.time_ns() // 1_000_000,
                "results": results,
            }
            atomic(CHECKPOINT, checkpoint)
            if r["status"] == "HISTORICAL_KLINES_ACCESSIBLE":
                print(
                    "UNKNOWN_HISTORICAL_TRY_FOUND",
                    symbol,
                    "first_ms=", r.get("first_open_time_ms"),
                    flush=True,
                )
            elif r["status"] == "PROBE_ERROR":
                print("PROBE_ERROR", symbol, r.get("error"), flush=True)
            if i % 50 == 0:
                print(f"DISCOVERY_PROGRESS {i}/{len(candidates)}", flush=True)
            await asyncio.sleep(REQ_GAP)

    found = [
        {"symbol": s, **r}
        for s, r in sorted(results.items())
        if r.get("status") == "HISTORICAL_KLINES_ACCESSIBLE"
    ]
    errors = [
        {"symbol": s, **r}
        for s, r in sorted(results.items())
        if r.get("status") == "PROBE_ERROR"
    ]

    out = {
        "schema_version": 1,
        "status": "PASS" if not errors else "PASS_WITH_PROBE_ERRORS",
        "generated_at_ms": time.time_ns() // 1_000_000,
        "candidate_source": "BINANCE_GLOBAL_CURRENT_BASE_ASSETS_AS_DISCOVERY_SEED",
        "candidate_source_url": global_source,
        "candidate_source_errors": source_errors,
        "binance_tr_probe_source": TR_KLINES,
        "global_base_assets_total": len(bases),
        "current_try_excluded": len(cur),
        "known_historical_excluded": len(known),
        "candidates_total": len(candidates),
        "candidates_checked": len(results),
        "unknown_historical_try_found": len(found),
        "probe_error_count": len(errors),
        "found": found,
        "probe_errors": errors,
        "canonicalized_automatically": False,
        "next_rule": (
            "Every discovered market must be matched to Binance TR official listing/"
            "delisting/transition evidence before canonical historical-universe inclusion."
        ),
        "backfills_touched": False,
        "collector_touched": False,
    }
    atomic(OUT, out)
    checkpoint["status"] = "COMPLETE"
    checkpoint["completed_at_ms"] = time.time_ns() // 1_000_000
    atomic(CHECKPOINT, checkpoint)
    print(json.dumps(out, ensure_ascii=False, indent=2))

asyncio.run(main())
PY

"$PY" -m py_compile "$ROOT/app/discover_unknown_historical_try.py"
"$PY" "$ROOT/app/discover_unknown_historical_try.py"

echo
echo '========== UNKNOWN HISTORICAL TRY =========='
"$PY" - <<'PY'
import json
from pathlib import Path
p=Path("/root/bintrbot/state/phase0a_unknown_historical_try_discovery.json")
x=json.loads(p.read_text())
for k in (
  "status","global_base_assets_total","current_try_excluded",
  "known_historical_excluded","candidates_total","candidates_checked",
  "unknown_historical_try_found","probe_error_count"
):
    print(f"{k.upper()}=",x.get(k))
print()
for r in x.get("found",[]):
    print("FOUND",r["symbol"],"first_open_time_ms=",r.get("first_open_time_ms"))
PY

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true
systemctl is-active bintrbot-collector.service || true
echo "PHASE0A_UNKNOWN_HISTORICAL_DISCOVERY=PASS"
