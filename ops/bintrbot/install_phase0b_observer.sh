#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/phase0b_observer.py" <<'PY'
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/root/bintrbot")
BASE = ROOT / "data/bronze/klines_1m"
STATE = ROOT / "state/backfill_klines.json"

manifests = sorted(BASE.glob("symbol=*/year=*/month=*/manifest.json"))

total = 0
complete = 0
rows = 0
gap_files = []
dup_files = []
checksum_missing = []
month_gap_counts = Counter()
month_gap_minutes = defaultdict(list)

for p in manifests:
    total += 1
    try:
        x = json.loads(p.read_text())
    except Exception as e:
        print("BAD_MANIFEST", p, repr(e))
        continue

    if x.get("status") == "COMPLETE":
        complete += 1
    rows += int(x.get("row_count") or 0)

    symbol = x.get("symbol")
    ym = x.get("year_month")
    gaps = int(x.get("gap_count") or 0)
    largest = int(x.get("largest_gap_minutes") or 0)
    dups = int(x.get("duplicate_count_removed") or 0)

    if gaps:
        gap_files.append({
            "symbol": symbol,
            "month": ym,
            "gap_count": gaps,
            "largest_gap_minutes": largest,
            "rows": int(x.get("row_count") or 0),
        })
        month_gap_counts[ym] += 1
        month_gap_minutes[ym].append(largest)

    if dups:
        dup_files.append({
            "symbol": symbol,
            "month": ym,
            "duplicates_removed": dups,
        })

    if x.get("row_count") and not x.get("sha256"):
        checksum_missing.append(f"{symbol}/{ym}")

state = {}
if STATE.exists():
    try:
        state = json.loads(STATE.read_text())
    except Exception:
        pass

print("========== PHASE 0B OBSERVER ==========")
print("BACKFILL_STATUS=", state.get("status"))
print("SYMBOLS_TOTAL=", state.get("symbols_total"))
print("MONTHS_COMPLETE_THIS_RUN=", state.get("months_complete_this_run"))
print("JOBS_REMAINING=", state.get("jobs_remaining"))
print("ERRORS=", len(state.get("errors") or {}))
print()
print("MANIFESTS_TOTAL=", total)
print("MANIFESTS_COMPLETE=", complete)
print("ROWS_IN_MANIFESTS=", rows)
print("GAP_FILES=", len(gap_files))
print("DUPLICATE_FILES=", len(dup_files))
print("CHECKSUM_MISSING_WITH_DATA=", len(checksum_missing))

print()
print("========== GAP FILES ==========")
if not gap_files:
    print("NONE")
else:
    for x in sorted(gap_files, key=lambda z: (z["month"] or "", z["symbol"] or "")):
        print(
            f'{x["symbol"]} {x["month"]} '
            f'gaps={x["gap_count"]} '
            f'largest_gap_minutes={x["largest_gap_minutes"]} '
            f'rows={x["rows"]}'
        )

print()
print("========== REPEATED GAP MONTHS ==========")
repeated = False
for ym, n in sorted(month_gap_counts.items()):
    if n >= 2:
        repeated = True
        vals = month_gap_minutes[ym]
        print(
            f'{ym} affected_markets={n} '
            f'largest_gap_minutes_values={sorted(set(vals))}'
        )
if not repeated:
    print("NONE")

print()
print("========== DUPLICATES ==========")
if not dup_files:
    print("NONE")
else:
    for x in dup_files[:100]:
        print(f'{x["symbol"]} {x["month"]} removed={x["duplicates_removed"]}')

print()
print("========== CHECKSUM ISSUES ==========")
if not checksum_missing:
    print("NONE")
else:
    for x in checksum_missing[:100]:
        print(x)
PY

cat > "$ROOT/phase0b-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
/root/bintrbot/.venv/bin/python /root/bintrbot/app/phase0b_observer.py
echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-aggtrades.service || true
echo
echo '========== DISK =========='
df -h /
SH

chmod +x "$ROOT/phase0b-status.sh"
"$ROOT/phase0b-status.sh"
