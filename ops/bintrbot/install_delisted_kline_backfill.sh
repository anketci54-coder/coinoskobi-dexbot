#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

mkdir -p "$ROOT/app" "$ROOT/state" "$ROOT/data/bronze/klines_1m"

cat > "$ROOT/app/backfill_delisted_klines.py" <<'PY'
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiohttp
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path("/root/bintrbot")
UNIVERSE = ROOT / "state/phase0a_historical_universe.json"
PROBE = ROOT / "state/phase0a_delisted_kline_probe.json"
CURRENT = ROOT / "data/meta/symbols.json"
OUT = ROOT / "data/bronze/klines_1m"
STATE = ROOT / "state/backfill_delisted_klines.json"

URL = "https://api.binance.me/api/v1/klines"
REQ_GAP = 0.65
MIN_FREE = 25 * 1024**3

SCHEMA = pa.schema([
    ("symbol", pa.string()),
    ("symbol_type", pa.int8()),
    ("open_time_ms", pa.int64()),
    ("open", pa.string()),
    ("high", pa.string()),
    ("low", pa.string()),
    ("close", pa.string()),
    ("volume", pa.string()),
    ("close_time_ms", pa.int64()),
    ("quote_volume", pa.string()),
    ("trade_count", pa.int64()),
    ("taker_buy_base_volume", pa.string()),
    ("taker_buy_quote_volume", pa.string()),
    ("ignore", pa.string()),
])

def now_ms():
    return time.time_ns() // 1_000_000

def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def local_tr_to_utc_ms(s: str | None):
    if not s:
        return None
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M")
    dt = dt.replace(tzinfo=timezone(timedelta(hours=3)))
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)

def month_key(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")

def next_ym(ym):
    y, m = map(int, ym.split("-"))
    return f"{y+1:04d}-01" if m == 12 else f"{y:04d}-{m+1:02d}"

def months(a, b):
    cur = a
    while True:
        yield cur
        if cur == b:
            break
        cur = next_ym(cur)

def bounds(ym):
    y, m = map(int, ym.split("-"))
    a = datetime(y, m, 1, tzinfo=timezone.utc)
    b = datetime(y + (m == 12), 1 if m == 12 else m + 1, 1, tzinfo=timezone.utc)
    return int(a.timestamp() * 1000), int(b.timestamp() * 1000) - 1

def manifest_path(symbol, ym):
    y, m = ym.split("-")
    return OUT / f"symbol={symbol}" / f"year={y}" / f"month={m}" / "manifest.json"

def done(symbol, ym):
    p = manifest_path(symbol, ym)
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text()).get("status") == "COMPLETE"
    except Exception:
        return False

async def get(session, params):
    last = None
    for n in range(10):
        if shutil.disk_usage("/").free < MIN_FREE:
            raise RuntimeError("DISK_GUARD_STOP")
        try:
            async with session.get(
                URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                text = await r.text()
                if r.status == 200:
                    x = json.loads(text)
                    return x.get("data", x) if isinstance(x, dict) else x
                if r.status in (418, 429):
                    await asyncio.sleep(min(10 * (n + 1), 120))
                    continue
                if r.status >= 500:
                    await asyncio.sleep(min(2 ** n, 30))
                    continue
                raise RuntimeError(f"HTTP_{r.status}:{text[:200]}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last = repr(e)
            await asyncio.sleep(min(2 ** n, 30))
        finally:
            await asyncio.sleep(REQ_GAP)
    raise RuntimeError(f"RETRY_EXHAUSTED:{last}")

async def fetch_month(session, symbol, ym, first_ms, end_exclusive):
    a, b = bounds(ym)
    start = max(a, first_ms)
    end = min(b, end_exclusive - 1)
    if start > end:
        return [], start, end

    api = symbol.replace("_", "")
    rows = []
    cursor = start

    while cursor <= end:
        data = await get(session, {
            "symbol": api,
            "interval": "1m",
            "startTime": cursor,
            "endTime": end,
            "limit": 1000,
        })
        if not isinstance(data, list) or not data:
            break

        batch = [r for r in data if isinstance(r, list) and len(r) >= 11]
        if not batch:
            break
        rows.extend(batch)

        last_open = int(batch[-1][0])
        nxt = last_open + 60_000
        if nxt <= cursor:
            raise RuntimeError(f"NON_ADVANCING_CURSOR:{symbol}:{ym}:{cursor}")
        cursor = nxt

        if len(batch) < 1000:
            break

    return rows, start, end

def write_month(symbol, ym, rows, req_start, req_end):
    y, m = ym.split("-")
    folder = OUT / f"symbol={symbol}" / f"year={y}" / f"month={m}"
    folder.mkdir(parents=True, exist_ok=True)
    datafile = folder / "klines.parquet"
    manifest = folder / "manifest.json"

    rows.sort(key=lambda r: int(r[0]))
    seen = set()
    dedup = []
    duplicates = 0
    gaps = 0
    largest = 0
    prev = None

    for r in rows:
        ot = int(r[0])
        if ot in seen:
            duplicates += 1
            continue
        seen.add(ot)
        if prev is not None and ot - prev > 60_000:
            gaps += 1
            largest = max(largest, (ot - prev) // 60_000 - 1)
        prev = ot
        dedup.append({
            "symbol": symbol,
            "symbol_type": 1,
            "open_time_ms": ot,
            "open": str(r[1]),
            "high": str(r[2]),
            "low": str(r[3]),
            "close": str(r[4]),
            "volume": str(r[5]),
            "close_time_ms": int(r[6]),
            "quote_volume": str(r[7]),
            "trade_count": int(r[8]),
            "taker_buy_base_volume": str(r[9]),
            "taker_buy_quote_volume": str(r[10]),
            "ignore": str(r[11]) if len(r) > 11 else "",
        })

    checksum = None
    size = 0
    if dedup:
        tmp = folder / "klines.parquet.tmp"
        pq.write_table(
            pa.Table.from_pylist(dedup, schema=SCHEMA),
            tmp,
            compression="zstd",
            compression_level=6,
            write_statistics=True,
        )
        os.replace(tmp, datafile)
        checksum = digest(datafile)
        size = datafile.stat().st_size
    else:
        datafile.unlink(missing_ok=True)

    info = {
        "status": "COMPLETE",
        "symbol": symbol,
        "symbol_type": 1,
        "interval": "1m",
        "year_month": ym,
        "row_count": len(dedup),
        "duplicate_count_removed": duplicates,
        "gap_count": gaps,
        "largest_gap_minutes": largest,
        "first_open_time_ms": dedup[0]["open_time_ms"] if dedup else None,
        "last_open_time_ms": dedup[-1]["open_time_ms"] if dedup else None,
        "requested_start_ms": req_start,
        "requested_end_ms": req_end,
        "sha256": checksum,
        "file_bytes": size,
        "source": URL,
        "universe_scope": "HISTORICAL_DELISTED_TRY",
        "completed_at_ms": now_ms(),
    }
    atomic_json(manifest, info)
    return info

async def main():
    universe = load(UNIVERSE, {})
    probe = load(PROBE, {})
    current = load(CURRENT, {})

    current_symbols = {
        str(x.get("symbol", "")).upper()
        for x in current.get("symbols", [])
        if isinstance(x, dict)
    }
    seed = {
        x["symbol"]: x
        for x in universe.get("confirmed_delisted_try_seed", [])
        if isinstance(x, dict) and x.get("symbol")
    }
    probe_map = {
        x["symbol"]: x
        for x in probe.get("results", [])
        if isinstance(x, dict)
        and x.get("status") == "HISTORICAL_KLINES_ACCESSIBLE"
        and x.get("first_open_time_ms") is not None
    }

    overlap = sorted(set(seed) & current_symbols)
    targets = []

    for symbol, meta in sorted(seed.items()):
        if symbol in current_symbols:
            continue
        pr = probe_map.get(symbol)
        if not pr:
            continue
        first_ms = int(pr["first_open_time_ms"])
        end_ms = local_tr_to_utc_ms(meta.get("delisted_local"))
        if end_ms is None or end_ms <= first_ms:
            continue
        targets.append((symbol, first_ms, end_ms))

    jobs = []
    for symbol, first_ms, end_ms in targets:
        for ym in months(month_key(first_ms), month_key(end_ms - 1)):
            if not done(symbol, ym):
                jobs.append((symbol, ym, first_ms, end_ms))

    state = load(STATE, {})
    state.update({
        "schema_version": 1,
        "status": "RUNNING",
        "started_at_ms": state.get("started_at_ms") or now_ms(),
        "targets_total": len(targets),
        "current_universe_overlap_excluded": overlap,
        "jobs_remaining_at_start": len(jobs),
        "jobs_remaining": len(jobs),
        "months_complete_this_run": 0,
        "rows_written_this_run": 0,
        "errors": {},
        "worker_count": 1,
        "request_gap_seconds": REQ_GAP,
        "disk_guard_gib": 25,
    })
    atomic_json(STATE, state)

    async with aiohttp.ClientSession(
        headers={"User-Agent": "bintrbot-delisted-kline-backfill/1.0"}
    ) as session:
        for idx, (symbol, ym, first_ms, end_ms) in enumerate(jobs, 1):
            try:
                rows, req_start, req_end = await fetch_month(
                    session, symbol, ym, first_ms, end_ms
                )
                info = write_month(symbol, ym, rows, req_start, req_end)

                state["months_complete_this_run"] += 1
                state["rows_written_this_run"] += int(info["row_count"])
                state["last_symbol"] = symbol
                state["last_month"] = ym
                state["jobs_remaining"] = len(jobs) - idx
                state["updated_at_ms"] = now_ms()
                atomic_json(STATE, state)

                print(
                    "DELISTED_MONTH_OK",
                    symbol,
                    ym,
                    f'rows={info["row_count"]}',
                    f'gaps={info["gap_count"]}',
                    flush=True,
                )
            except Exception as e:
                state["errors"][f"{symbol}:{ym}"] = repr(e)
                state["status"] = "FAILED"
                state["updated_at_ms"] = now_ms()
                atomic_json(STATE, state)
                raise

    state["status"] = "COMPLETE"
    state["jobs_remaining"] = 0
    state["completed_at_ms"] = now_ms()
    atomic_json(STATE, state)
    print("DELISTED_BACKFILL_COMPLETE", flush=True)

asyncio.run(main())
PY

cat > /etc/systemd/system/bintrbot-backfill-delisted-klines.service <<'UNIT'
[Unit]
Description=BintrBot Historical Delisted TRY 1m Kline Backfill
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/backfill_delisted_klines.py
User=root
Nice=19
IOSchedulingClass=idle
Restart=on-failure
RestartSec=30
Environment=PYTHONUNBUFFERED=1
UNIT

cat > "$ROOT/delisted-history-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
echo '========== DELISTED HISTORICAL BACKFILL =========='
systemctl is-active bintrbot-backfill-delisted-klines.service || true
cat /root/bintrbot/state/backfill_delisted_klines.json 2>/dev/null || echo 'state missing'
echo
echo '========== MAIN BACKFILL =========='
systemctl is-active bintrbot-backfill-klines.service || true
echo
echo '========== LIVE =========='
systemctl is-active bintrbot-collector.service || true
echo
echo '========== DISK =========='
df -h /
echo
echo '========== RECENT LOG =========='
journalctl -u bintrbot-backfill-delisted-klines.service --no-pager -n 25
SH

chmod +x "$ROOT/delisted-history-status.sh"

"$PY" -m py_compile "$ROOT/app/backfill_delisted_klines.py"
systemctl daemon-reload
systemctl enable --now bintrbot-backfill-delisted-klines.service

sleep 3
"$ROOT/delisted-history-status.sh"
