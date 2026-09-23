#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

mkdir -p "$ROOT/app" "$ROOT/state" "$ROOT/data/quality"

cat > "$ROOT/app/phase1a_kline_audit.py" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path("/root/bintrbot")
BASE = ROOT / "data/bronze/klines_1m"
DB = ROOT / "state/phase1a_kline_audit.sqlite3"
STATE = ROOT / "state/phase1a_kline_audit.json"

DEC = pa.decimal128(38, 18)

def now_ms() -> int:
    return time.time_ns() // 1_000_000

def atomic_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

con = sqlite3.connect(DB)
con.execute("""
CREATE TABLE IF NOT EXISTS audit_results (
    file TEXT NOT NULL,
    expected_sha256 TEXT NOT NULL,
    audited_at_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    row_count INTEGER,
    actual_sha256 TEXT,
    checksum_ok INTEGER,
    timestamp_order_ok INTEGER,
    duplicate_count INTEGER,
    gap_count INTEGER,
    manifest_gap_count INTEGER,
    manifest_gap_match INTEGER,
    impossible_ohlc_count INTEGER,
    invalid_volume_count INTEGER,
    error TEXT,
    PRIMARY KEY(file, expected_sha256)
)
""")
con.commit()

manifests = sorted(BASE.glob("symbol=*/year=*/month=*/manifest.json"))
scanned = skipped = audited = pass_count = fail_count = 0
last_file = None

for mp in manifests:
    scanned += 1
    try:
        m = json.loads(mp.read_text())
    except Exception:
        continue

    if m.get("status") != "COMPLETE":
        continue

    p = mp.parent / "klines.parquet"
    expected = str(m.get("sha256") or "")
    if not p.exists() or not expected:
        continue

    rel = str(p.relative_to(ROOT))
    last_file = rel

    row = con.execute(
        "SELECT status FROM audit_results WHERE file=? AND expected_sha256=?",
        (rel, expected),
    ).fetchone()
    if row is not None:
        skipped += 1
        continue

    status = "PASS"
    err = None
    row_count = actual_sha = checksum_ok = order_ok = dup_count = gap_count = None
    manifest_gap_count = int(m.get("gap_count") or 0)
    gap_match = impossible = bad_volume = None

    try:
        actual_sha = sha256(p)
        checksum_ok = int(actual_sha == expected)

        table = pq.read_table(
            p,
            columns=["open_time_ms", "open", "high", "low", "close", "volume"],
        )
        row_count = table.num_rows

        ts = table["open_time_ms"].combine_chunks()
        pyts = ts.to_pylist()

        order_ok = int(all(pyts[i] < pyts[i + 1] for i in range(len(pyts) - 1)))
        dup_count = len(pyts) - len(set(pyts))
        gap_count = sum(
            1 for i in range(len(pyts) - 1)
            if pyts[i + 1] - pyts[i] > 60_000
        )
        gap_match = int(gap_count == manifest_gap_count)

        o = pc.cast(table["open"].combine_chunks(), DEC, safe=False)
        h = pc.cast(table["high"].combine_chunks(), DEC, safe=False)
        l = pc.cast(table["low"].combine_chunks(), DEC, safe=False)
        c = pc.cast(table["close"].combine_chunks(), DEC, safe=False)
        v = pc.cast(table["volume"].combine_chunks(), DEC, safe=False)

        high_bad = pc.or_(
            pc.less(h, o),
            pc.or_(pc.less(h, c), pc.less(h, l)),
        )
        low_bad = pc.or_(
            pc.greater(l, o),
            pc.or_(pc.greater(l, c), pc.greater(l, h)),
        )
        impossible = int(pc.sum(pc.cast(pc.or_(high_bad, low_bad), pa.int64())).as_py() or 0)
        bad_volume = int(pc.sum(pc.cast(pc.less(v, pa.scalar(0, type=DEC)), pa.int64())).as_py() or 0)

        manifest_rows = int(m.get("row_count") or 0)
        if (
            not checksum_ok
            or not order_ok
            or dup_count != 0
            or not gap_match
            or impossible != 0
            or bad_volume != 0
            or row_count != manifest_rows
        ):
            status = "FAIL"

    except Exception as e:
        status = "FAIL"
        err = repr(e)[:1000]

    con.execute(
        """
        INSERT INTO audit_results(
            file, expected_sha256, audited_at_ms, status, row_count,
            actual_sha256, checksum_ok, timestamp_order_ok,
            duplicate_count, gap_count, manifest_gap_count,
            manifest_gap_match, impossible_ohlc_count,
            invalid_volume_count, error
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            rel, expected, now_ms(), status, row_count,
            actual_sha, checksum_ok, order_ok, dup_count,
            gap_count, manifest_gap_count, gap_match,
            impossible, bad_volume, err,
        ),
    )
    con.commit()
    audited += 1
    if status == "PASS":
        pass_count += 1
    else:
        fail_count += 1

total_audited = con.execute("SELECT COUNT(*) FROM audit_results").fetchone()[0]
total_pass = con.execute("SELECT COUNT(*) FROM audit_results WHERE status='PASS'").fetchone()[0]
total_fail = con.execute("SELECT COUNT(*) FROM audit_results WHERE status='FAIL'").fetchone()[0]

failures = [
    {
        "file": r[0],
        "error": r[1],
        "checksum_ok": r[2],
        "timestamp_order_ok": r[3],
        "duplicate_count": r[4],
        "gap_count": r[5],
        "manifest_gap_count": r[6],
        "manifest_gap_match": r[7],
        "impossible_ohlc_count": r[8],
        "invalid_volume_count": r[9],
    }
    for r in con.execute(
        """
        SELECT file,error,checksum_ok,timestamp_order_ok,duplicate_count,
               gap_count,manifest_gap_count,manifest_gap_match,
               impossible_ohlc_count,invalid_volume_count
        FROM audit_results
        WHERE status='FAIL'
        ORDER BY audited_at_ms DESC
        LIMIT 50
        """
    )
]

con.close()

state = {
    "schema_version": 1,
    "status": "PASS" if total_fail == 0 else "FAIL",
    "completed_at_ms": now_ms(),
    "manifests_seen_this_run": scanned,
    "already_audited_this_run": skipped,
    "newly_audited_this_run": audited,
    "new_pass_this_run": pass_count,
    "new_fail_this_run": fail_count,
    "audited_versions_total": total_audited,
    "pass_total": total_pass,
    "fail_total": total_fail,
    "last_file": last_file,
    "checks": [
        "SHA256",
        "PARQUET_READ",
        "ROW_COUNT",
        "TIMESTAMP_STRICT_ORDER",
        "DUPLICATE_TIMESTAMP",
        "GAP_COUNT_VS_MANIFEST",
        "OHLC_INVARIANTS",
        "NEGATIVE_VOLUME",
    ],
    "known_source_gaps_are_not_failures_if_manifest_matches": True,
    "failures": failures,
}
atomic_json(STATE, state)
print(json.dumps(state, ensure_ascii=False, indent=2))
PY

cat > /etc/systemd/system/bintrbot-phase1a-audit.service <<'UNIT'
[Unit]
Description=BintrBot Incremental Historical Kline Audit
After=local-fs.target

[Service]
Type=oneshot
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/phase1a_kline_audit.py
User=root
Nice=19
IOSchedulingClass=idle
UNIT

cat > /etc/systemd/system/bintrbot-phase1a-audit.timer <<'UNIT'
[Unit]
Description=Run BintrBot Historical Kline Audit Periodically

[Timer]
OnBootSec=10min
OnUnitActiveSec=15min
AccuracySec=1min
Persistent=true
Unit=bintrbot-phase1a-audit.service

[Install]
WantedBy=timers.target
UNIT

cat > "$ROOT/phase1a-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
echo '========== PHASE 1A AUDIT =========='
cat /root/bintrbot/state/phase1a_kline_audit.json 2>/dev/null || echo 'audit state not written yet'
echo
echo '========== SERVICE =========='
systemctl is-active bintrbot-phase1a-audit.service || true
systemctl is-active bintrbot-phase1a-audit.timer || true
echo
echo '========== BACKFILL UNAFFECTED =========='
systemctl is-active bintrbot-backfill-klines.service || true
/root/bintrbot/history-status.sh 2>/dev/null | head -20 || true
SH

chmod +x "$ROOT/phase1a-status.sh"

systemctl daemon-reload
systemctl enable --now bintrbot-phase1a-audit.timer
systemctl start --no-block bintrbot-phase1a-audit.service

echo 'PHASE1A_AUDIT_INSTALLED=YES'
echo 'AUDIT_MODE=INCREMENTAL_LOW_PRIORITY'
echo 'BACKFILL_RESTARTED=NO'
echo 'LIVE_COLLECTOR_RESTARTED=NO'
echo
"$ROOT/phase1a-status.sh"
