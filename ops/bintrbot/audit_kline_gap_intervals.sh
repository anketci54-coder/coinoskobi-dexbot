#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/audit_kline_gap_intervals.py" <<'PY'
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path("/root/bintrbot")
BASE = ROOT / "data/bronze/klines_1m"

def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat()

gap_rows = []
groups = defaultdict(list)

for manifest in sorted(BASE.glob("symbol=*/year=*/month=*/manifest.json")):
    try:
        m = json.loads(manifest.read_text())
    except Exception:
        continue
    if int(m.get("gap_count") or 0) <= 0:
        continue

    parquet = manifest.parent / "klines.parquet"
    if not parquet.exists():
        continue

    t = pq.read_table(parquet, columns=["open_time_ms"]).column("open_time_ms").to_pylist()
    t = sorted(set(int(x) for x in t))

    prev = None
    for cur in t:
        if prev is not None and cur - prev > 60_000:
            missing = (cur - prev)//60_000 - 1
            start = prev + 60_000
            end = cur - 60_000
            row = {
                "symbol": m.get("symbol"),
                "month": m.get("year_month"),
                "missing_minutes": int(missing),
                "gap_start_ms": int(start),
                "gap_end_ms": int(end),
                "gap_start_utc": iso(start),
                "gap_end_utc": iso(end),
                "previous_candle_utc": iso(prev),
                "next_candle_utc": iso(cur),
            }
            gap_rows.append(row)
            groups[(start, end, missing)].append(m.get("symbol"))
        prev = cur

print("========== EXACT GAP INTERVALS ==========")
for r in gap_rows:
    print(
        f'{r["symbol"]} {r["month"]} '
        f'missing={r["missing_minutes"]} '
        f'{r["gap_start_utc"]} -> {r["gap_end_utc"]}'
    )

print()
print("========== SHARED EXACT GAPS ==========")
shared = False
for (start, end, missing), symbols in sorted(groups.items()):
    if len(symbols) >= 2:
        shared = True
        print(
            f'affected_markets={len(symbols)} '
            f'missing={missing} '
            f'{iso(start)} -> {iso(end)}'
        )
        print("symbols=" + ",".join(sorted(symbols)))
if not shared:
    print("NONE")

print()
print("========== SUMMARY ==========")
print("GAP_INTERVALS_TOTAL=", len(gap_rows))
print("UNIQUE_INTERVALS=", len(groups))
print("SHARED_INTERVALS=", sum(1 for v in groups.values() if len(v) >= 2))
PY

"$PY" "$ROOT/app/audit_kline_gap_intervals.py"
