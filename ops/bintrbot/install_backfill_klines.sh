#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"

test -x "$PY" || { echo "ABORT: bintrbot venv yok"; exit 1; }
test -s "$ROOT/data/meta/symbols.json" || { echo "ABORT: symbols.json yok"; exit 1; }

"$PIP" install -q pyarrow

mkdir -p "$ROOT/app" "$ROOT/data/bronze/klines_1m" "$ROOT/state"

cat > "$ROOT/app/backfill_klines.py" <<'PY'
from __future__ import annotations

import asyncio, hashlib, json, os, shutil, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path("/root/bintrbot")
META = ROOT / "data/meta/symbols.json"
OUT = ROOT / "data/bronze/klines_1m"
STATE = ROOT / "state/backfill_klines.json"

START_MS = 1599609600000  # 2020-09-09 00:00:00 UTC
MIN_FREE = 15 * 1024**3
WORKERS = 3
REQ_GAP = 0.35

URL = {
    1: "https://api.binance.me/api/v1/klines",
    3: "https://cloudme-tr.2meta.app/api/v1/klines",
}

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

rate_lock = asyncio.Lock()
next_req = 0.0
state_lock = asyncio.Lock()
halt = asyncio.Event()

def now_ms():
    return time.time_ns() // 1_000_000

def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    os.replace(tmp, path)

def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def free_ok():
    free = shutil.disk_usage("/").free
    if free < MIN_FREE:
        halt.set()
        return False
    return True

async def throttle():
    global next_req
    async with rate_lock:
        now = time.monotonic()
        if next_req > now:
            await asyncio.sleep(next_req - now)
        next_req = max(time.monotonic(), next_req) + REQ_GAP

async def fetch(session, url, params):
    last = None
    for n in range(10):
        if halt.is_set():
            raise RuntimeError("DISK_GUARD_STOP")
        await throttle()
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 200:
                    x = await r.json(content_type=None)
                    return x.get("data", x) if isinstance(x, dict) else x
                body = await r.text()
                if r.status in (418, 429):
                    await asyncio.sleep(min(15 * (n + 1), 120))
                    continue
                if 500 <= r.status < 600:
                    await asyncio.sleep(min(2 ** n, 30))
                    continue
                raise RuntimeError(f"HTTP_{r.status}:{body[:200]}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last = repr(e)
            await asyncio.sleep(min(2 ** n, 30))
    raise RuntimeError(f"RETRY_EXHAUSTED:{last}")

def month_key(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")

def month_bounds(ym):
    y, m = map(int, ym.split("-"))
    a = datetime(y, m, 1, tzinfo=timezone.utc)
    b = datetime(y + (m == 12), 1 if m == 12 else m + 1, 1, tzinfo=timezone.utc)
    return int(a.timestamp() * 1000), int(b.timestamp() * 1000) - 1

def all_months(start_ms, end_ms):
    cur = month_key(start_ms)
    end = month_key(end_ms)
    out = []
    while True:
        out.append(cur)
        if cur == end:
            return out
        y, m = map(int, cur.split("-"))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
        cur = f"{y:04d}-{m:02d}"

def manifest_path(symbol, ym):
    y, m = ym.split("-")
    return OUT / f"symbol={symbol}" / f"year={y}" / f"month={m}" / "manifest.json"

def is_complete(symbol, ym):
    p = manifest_path(symbol, ym)
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text()).get("status") == "COMPLETE"
    except Exception:
        return False

def write_month(symbol, stype, ym, rows, source, req_start, req_end):
    y, m = ym.split("-")
    folder = OUT / f"symbol={symbol}" / f"year={y}" / f"month={m}"
    folder.mkdir(parents=True, exist_ok=True)
    datafile = folder / "klines.parquet"
    manifest = folder / "manifest.json"

    rows.sort(key=lambda r: int(r[0]))
    dedup = []
    seen = set()
    duplicates = 0
    gaps = 0
    largest_gap = 0
    prev = None

    for r in rows:
        ot = int(r[0])
        if ot in seen:
            duplicates += 1
            continue
        seen.add(ot)
        if prev is not None and ot - prev > 60000:
            gaps += 1
            largest_gap = max(largest_gap, (ot - prev) // 60000 - 1)
        prev = ot
        dedup.append({
            "symbol": symbol,
            "symbol_type": stype,
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

    if dedup:
        tmp = folder / "klines.parquet.tmp"
        pq.write_table(pa.Table.from_pylist(dedup, schema=SCHEMA), tmp, compression="zstd", compression_level=6)
        os.replace(tmp, datafile)
        checksum = sha256(datafile)
        size = datafile.stat().st_size
        first_ms = dedup[0]["open_time_ms"]
        last_ms = dedup[-1]["open_time_ms"]
    else:
        datafile.unlink(missing_ok=True)
        checksum = None
        size = 0
        first_ms = None
        last_ms = None

    info = {
        "status": "COMPLETE",
        "symbol": symbol,
        "symbol_type": stype,
        "interval": "1m",
        "year_month": ym,
        "row_count": len(dedup),
        "duplicate_count_removed": duplicates,
        "gap_count": gaps,
        "largest_gap_minutes": largest_gap,
        "first_open_time_ms": first_ms,
        "last_open_time_ms": last_ms,
        "requested_start_ms": req_start,
        "requested_end_ms": req_end,
        "sha256": checksum,
        "file_bytes": size,
        "source": source,
        "completed_at_ms": now_ms(),
    }
    atomic_json(manifest, info)
    return info

async def download_month(session, symbol, api_symbol, stype, ym, cutoff):
    a, b = month_bounds(ym)
    a = max(a, START_MS)
    b = min(b, cutoff)
    cursor = a
    rows = []
    source = URL[stype]

    while cursor <= b:
        if not free_ok():
            raise RuntimeError("DISK_GUARD_STOP")
        data = await fetch(session, source, {
            "symbol": api_symbol,
            "interval": "1m",
            "startTime": cursor,
            "endTime": b,
            "limit": 1000,
        })
        if not isinstance(data, list) or not data:
            break
        valid = [r for r in data if isinstance(r, list) and len(r) >= 11 and a <= int(r[0]) <= b]
        if not valid:
            break
        rows.extend(valid)
        nxt = int(valid[-1][0]) + 60000
        if nxt <= cursor:
            raise RuntimeError("NON_ADVANCING_CURSOR")
        cursor = nxt
        if len(data) < 1000:
            break

    return await asyncio.to_thread(write_month, symbol, stype, ym, rows, source, a, b)

async def main():
    meta = json.loads(META.read_text())
    symbols = meta.get("symbols", [])
    cutoff = (now_ms() // 60000) * 60000 - 1

    jobs = asyncio.Queue()
    total_jobs = 0

    for row in symbols:
        stype = int(row.get("type", 1))
        if stype not in URL:
            continue
        symbol = str(row["symbol"])
        api_symbol = symbol.replace("_", "") if stype == 1 else symbol
        for ym in all_months(START_MS, cutoff):
            if not is_complete(symbol, ym):
                await jobs.put((symbol, api_symbol, stype, ym))
                total_jobs += 1

    progress = {
        "status": "RUNNING",
        "started_at_ms": now_ms(),
        "cutoff_ms": cutoff,
        "symbols_total": len(symbols),
        "jobs_remaining_at_start": total_jobs,
        "months_complete_this_run": 0,
        "rows_written_this_run": 0,
        "errors": {},
    }
    atomic_json(STATE, progress)

    async with aiohttp.ClientSession(headers={"User-Agent": "bintrbot-historical/1.0"}) as session:
        async def worker(n):
            while not halt.is_set():
                try:
                    symbol, api_symbol, stype, ym = jobs.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    info = await download_month(session, symbol, api_symbol, stype, ym, cutoff)
                    async with state_lock:
                        progress["months_complete_this_run"] += 1
                        progress["rows_written_this_run"] += int(info["row_count"])
                        progress["last_symbol"] = symbol
                        progress["last_month"] = ym
                        progress["updated_at_ms"] = now_ms()
                        atomic_json(STATE, progress)
                    print("MONTH_OK", symbol, ym, f"rows={info['row_count']}", f"gaps={info['gap_count']}", flush=True)
                except Exception as e:
                    if str(e) == "DISK_GUARD_STOP":
                        halt.set()
                    else:
                        async with state_lock:
                            progress["errors"][f"{symbol}:{ym}"] = repr(e)
                            atomic_json(STATE, progress)
                        print("MONTH_ERROR", symbol, ym, repr(e), flush=True)
                finally:
                    jobs.task_done()

        await asyncio.gather(*(worker(i) for i in range(WORKERS)))

    if halt.is_set():
        progress["status"] = "DISK_GUARD_STOP"
        progress["free_bytes"] = shutil.disk_usage("/").free
    elif progress["errors"]:
        progress["status"] = "INCOMPLETE_ERRORS"
    else:
        progress["status"] = "COMPLETE"

    progress["finished_at_ms"] = now_ms()
    atomic_json(STATE, progress)
    print("BACKFILL_STATUS", progress["status"], flush=True)

asyncio.run(main())
PY

cat > /etc/systemd/system/bintrbot-backfill-klines.service <<'UNIT'
[Unit]
Description=Binance TR Historical 1m Kline Backfill
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/backfill_klines.py
Restart=no
User=root
Environment=PYTHONUNBUFFERED=1
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7

[Install]
WantedBy=multi-user.target
UNIT

cat > /root/bintrbot/history-status.sh <<'SH'
#!/usr/bin/env bash
echo '========== LIVE =========='
systemctl is-active bintrbot-collector.service || true
echo '========== BACKFILL =========='
systemctl is-active bintrbot-backfill-klines.service || true
echo '========== STATE =========='
cat /root/bintrbot/state/backfill_klines.json 2>/dev/null || true
echo '========== DATA =========='
du -sh /root/bintrbot/data/bronze/klines_1m 2>/dev/null || true
find /root/bintrbot/data/bronze/klines_1m -name klines.parquet 2>/dev/null | wc -l
echo '========== DISK =========='
df -hT /
echo '========== LOG =========='
journalctl -u bintrbot-backfill-klines.service -n 30 --no-pager
SH
chmod +x /root/bintrbot/history-status.sh

systemctl daemon-reload
systemctl enable bintrbot-backfill-klines.service >/dev/null
systemctl restart bintrbot-backfill-klines.service

sleep 15
/root/bintrbot/history-status.sh
