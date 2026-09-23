#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/phase0b_gap_timestamps.py" <<'PY'
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path("/root/bintrbot")
BASE = ROOT / "data/bronze/klines_1m"

def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()

cases = []

for manifest_path in sorted(BASE.glob("symbol=*/year=*/month=*/manifest.json")):
    try:
        m = json.loads(manifest_path.read_text())
    except Exception:
        continue
    if int(m.get("gap_count") or 0) <= 0:
        continue

    data_path = manifest_path.parent / "klines.parquet"
    if not data_path.exists():
        continue

    table = pq.read_table(data_path, columns=["open_time_ms"])
    vals = sorted(int(x.as_py()) for x in table["open_time_ms"])

    for a, b in zip(vals, vals[1:]):
        diff = (b - a) // 60000
        if diff > 1:
            missing = diff - 1
            gap_start = a + 60000
            gap_end = b - 60000
            cases.append({
                "symbol": m.get("symbol"),
                "month": m.get("year_month"),
                "missing_minutes": missing,
                "prev_candle_ms": a,
                "next_candle_ms": b,
                "gap_start_ms": gap_start,
                "gap_end_ms": gap_end,
                "prev_candle_utc": iso(a),
                "gap_start_utc": iso(gap_start),
                "gap_end_utc": iso(gap_end),
                "next_candle_utc": iso(b),
            })

groups = defaultdict(list)
for c in cases:
    key = (c["gap_start_ms"], c["gap_end_ms"], c["missing_minutes"])
    groups[key].append(c["symbol"])

print("========== EXACT GAP WINDOWS ==========")
for c in cases:
    print(
        f'{c["symbol"]} {c["month"]} '
        f'missing={c["missing_minutes"]} '
        f'gap_start={c["gap_start_utc"]} '
        f'gap_end={c["gap_end_utc"]} '
        f'next={c["next_candle_utc"]}'
    )

print()
print("========== SHARED GAP WINDOWS ==========")
shared = False
for (start, end, missing), symbols in sorted(groups.items()):
    if len(symbols) >= 2:
        shared = True
        print(
            f'affected_markets={len(symbols)} '
            f'missing_minutes={missing} '
            f'gap_start={iso(start)} '
            f'gap_end={iso(end)} '
            f'symbols={",".join(sorted(symbols))}'
        )
if not shared:
    print("NONE")

out = {
    "status": "PASS",
    "gap_windows_total": len(cases),
    "shared_gap_windows": [
        {
            "gap_start_ms": start,
            "gap_end_ms": end,
            "gap_start_utc": iso(start),
            "gap_end_utc": iso(end),
            "missing_minutes": missing,
            "affected_markets": len(symbols),
            "symbols": sorted(symbols),
        }
        for (start, end, missing), symbols in groups.items()
        if len(symbols) >= 2
    ],
}
path = ROOT / "state/phase0b_exact_gaps.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print()
print("STATE=", path)
PY

"$PY" "$ROOT/app/phase0b_gap_timestamps.py"
