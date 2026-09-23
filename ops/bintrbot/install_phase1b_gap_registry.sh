#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

mkdir -p "$ROOT/app" "$ROOT/state" "$ROOT/data/quality"

cat > "$ROOT/app/phase1b_gap_registry.py" <<'PY'
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path("/root/bintrbot")
BASE = ROOT / "data/bronze/klines_1m"
DB = ROOT / "state/phase1b_gap_registry.sqlite3"
OUT = ROOT / "data/quality/gap_registry.json"
STATE = ROOT / "state/phase1b_gap_registry.json"

def now_ms():
    return time.time_ns() // 1_000_000

def iso(ms):
    return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat()

def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

con = sqlite3.connect(DB)
con.execute("""
CREATE TABLE IF NOT EXISTS gaps (
    symbol TEXT NOT NULL,
    year_month TEXT NOT NULL,
    gap_start_ms INTEGER NOT NULL,
    gap_end_ms INTEGER NOT NULL,
    missing_minutes INTEGER NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    classification TEXT NOT NULL,
    classification_reason TEXT NOT NULL,
    first_seen_at_ms INTEGER NOT NULL,
    last_seen_at_ms INTEGER NOT NULL,
    PRIMARY KEY(symbol, year_month, gap_start_ms, gap_end_ms, manifest_sha256)
)
""")
con.commit()

seen = 0
new = 0
now = now_ms()

for mp in sorted(BASE.glob("symbol=*/year=*/month=*/manifest.json")):
    try:
        m = json.loads(mp.read_text())
    except Exception:
        continue

    if m.get("status") != "COMPLETE":
        continue
    if int(m.get("gap_count") or 0) <= 0:
        continue

    p = mp.parent / "klines.parquet"
    if not p.exists():
        continue

    seen += 1
    ts = sorted(set(int(x) for x in pq.read_table(p, columns=["open_time_ms"])["open_time_ms"].to_pylist()))
    prev = None
    for cur in ts:
        if prev is not None and cur - prev > 60_000:
            start = prev + 60_000
            end = cur - 60_000
            missing = (cur - prev)//60_000 - 1
            symbol = str(m.get("symbol"))
            ym = str(m.get("year_month"))
            sha = str(m.get("sha256") or "")
            exists = con.execute(
                """SELECT 1 FROM gaps
                   WHERE symbol=? AND year_month=? AND gap_start_ms=? AND gap_end_ms=? AND manifest_sha256=?""",
                (symbol, ym, start, end, sha),
            ).fetchone()
            if not exists:
                new += 1
                con.execute(
                    """INSERT INTO gaps(
                        symbol,year_month,gap_start_ms,gap_end_ms,missing_minutes,
                        manifest_sha256,classification,classification_reason,
                        first_seen_at_ms,last_seen_at_ms
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        symbol, ym, start, end, int(missing), sha,
                        "UNCLASSIFIED",
                        "Requires source re-query and/or external outage evidence.",
                        now, now,
                    ),
                )
            else:
                con.execute(
                    """UPDATE gaps SET last_seen_at_ms=?
                       WHERE symbol=? AND year_month=? AND gap_start_ms=? AND gap_end_ms=? AND manifest_sha256=?""",
                    (now, symbol, ym, start, end, sha),
                )
        prev = cur

con.commit()

rows = list(con.execute("""
SELECT symbol,year_month,gap_start_ms,gap_end_ms,missing_minutes,
       classification,classification_reason
FROM gaps
ORDER BY gap_start_ms,symbol
"""))

groups = defaultdict(list)
for r in rows:
    groups[(r[2], r[3], r[4])].append(r[0])

shared = []
for (start, end, missing), symbols in sorted(groups.items()):
    if len(symbols) >= 2:
        shared.append({
            "gap_start_ms": start,
            "gap_end_ms": end,
            "gap_start_utc": iso(start),
            "gap_end_utc": iso(end),
            "missing_minutes": missing,
            "affected_markets": len(symbols),
            "symbols": sorted(symbols),
        })

entries = [
    {
        "symbol": r[0],
        "year_month": r[1],
        "gap_start_ms": r[2],
        "gap_end_ms": r[3],
        "gap_start_utc": iso(r[2]),
        "gap_end_utc": iso(r[3]),
        "missing_minutes": r[4],
        "classification": r[5],
        "classification_reason": r[6],
    }
    for r in rows
]

# Known 2023-03-24 shared interval gets a conservative correlation label only.
target_start = 1679661600000  # 2023-03-24 12:40:00 UTC
target_end = 1679666340000    # 2023-03-24 13:59:00 UTC
for item in entries:
    if item["gap_start_ms"] == target_start and item["gap_end_ms"] == target_end:
        item["classification"] = "EXCHANGE_OUTAGE_CORRELATED"
        item["classification_reason"] = (
            "Shared exact 80-minute interval across multiple Binance TR TRY markets; "
            "end aligns with documented Binance spot recovery at 14:00 UTC. "
            "Do not treat as definitively Binance TR-specific outage until source re-query/venue evidence is complete."
        )
        con.execute(
            """UPDATE gaps SET classification=?, classification_reason=?, last_seen_at_ms=?
               WHERE symbol=? AND gap_start_ms=? AND gap_end_ms=?""",
            (
                item["classification"], item["classification_reason"], now,
                item["symbol"], item["gap_start_ms"], item["gap_end_ms"],
            ),
        )

con.commit()
con.close()

out = {
    "schema_version": 1,
    "generated_at_ms": now,
    "generated_at_utc": iso(now),
    "gap_intervals_total": len(entries),
    "shared_exact_intervals": shared,
    "entries": entries,
}
atomic_json(OUT, out)

state = {
    "schema_version": 1,
    "status": "PASS",
    "generated_at_ms": now,
    "gap_manifest_files_seen": seen,
    "new_gap_intervals_this_run": new,
    "gap_intervals_total": len(entries),
    "shared_exact_interval_count": len(shared),
    "unclassified_count": sum(1 for x in entries if x["classification"] == "UNCLASSIFIED"),
    "exchange_outage_correlated_count": sum(1 for x in entries if x["classification"] == "EXCHANGE_OUTAGE_CORRELATED"),
    "source_requery_performed": False,
    "backfill_touched": False,
}
atomic_json(STATE, state)
print(json.dumps(state, ensure_ascii=False, indent=2))
PY

cat > /etc/systemd/system/bintrbot-phase1b-gap-registry.service <<'UNIT'
[Unit]
Description=BintrBot Historical Gap Registry
After=local-fs.target

[Service]
Type=oneshot
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/phase1b_gap_registry.py
User=root
Nice=19
IOSchedulingClass=idle
UNIT

cat > /etc/systemd/system/bintrbot-phase1b-gap-registry.timer <<'UNIT'
[Unit]
Description=Refresh BintrBot Historical Gap Registry

[Timer]
OnBootSec=12min
OnUnitActiveSec=30min
AccuracySec=2min
Persistent=true
Unit=bintrbot-phase1b-gap-registry.service

[Install]
WantedBy=timers.target
UNIT

cat > "$ROOT/phase1b-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
echo '========== PHASE 1B GAP REGISTRY =========='
cat /root/bintrbot/state/phase1b_gap_registry.json 2>/dev/null || echo 'state missing'
echo
echo '========== FIRST GAPS =========='
python3 - <<'PY'
import json
from pathlib import Path
p=Path("/root/bintrbot/data/quality/gap_registry.json")
if not p.exists():
    print("registry missing")
    raise SystemExit
x=json.loads(p.read_text())
for g in x.get("entries", [])[:30]:
    print(g["symbol"], g["gap_start_utc"], "->", g["gap_end_utc"], "missing=", g["missing_minutes"], g["classification"])
PY
echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-phase1b-gap-registry.timer || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-collector.service || true
SH

chmod +x "$ROOT/phase1b-status.sh"

systemctl daemon-reload
systemctl enable --now bintrbot-phase1b-gap-registry.timer
systemctl start bintrbot-phase1b-gap-registry.service

"$ROOT/phase1b-status.sh"
