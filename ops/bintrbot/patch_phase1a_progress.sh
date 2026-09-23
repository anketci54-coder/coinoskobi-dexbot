#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
APP="$ROOT/app/phase1a_kline_audit.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/state/phase1a_kline_audit.py.pre_progress.$TS.bak"

systemctl stop bintrbot-phase1a-audit.service 2>/dev/null || true
cp -a "$APP" "$BACKUP"

"$PY" - "$APP" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()
orig = s

# Add a bounded batch size so the audit remains incremental and low-impact.
needle = 'STATE = ROOT / "state/phase1a_kline_audit.json"\n\nDEC = pa.decimal128(38, 18)\n'
repl = 'STATE = ROOT / "state/phase1a_kline_audit.json"\n\nBATCH_MAX = 250\nPROGRESS_EVERY = 25\nDEC = pa.decimal128(38, 18)\n'
if needle not in s:
    raise SystemExit("PATCH_ABORT constants target missing")
s = s.replace(needle, repl, 1)

needle = 'manifests = sorted(BASE.glob("symbol=*/year=*/month=*/manifest.json"))\nscanned = skipped = audited = pass_count = fail_count = 0\nlast_file = None\n'
repl = '''manifests = sorted(BASE.glob("symbol=*/year=*/month=*/manifest.json"))
scanned = skipped = audited = pass_count = fail_count = 0
last_file = None
started = now_ms()

def write_progress(status: str) -> None:
    atomic_json(STATE, {
        "schema_version": 2,
        "status": status,
        "started_at_ms": started,
        "updated_at_ms": now_ms(),
        "manifests_seen_this_run": scanned,
        "already_audited_this_run": skipped,
        "newly_audited_this_run": audited,
        "new_pass_this_run": pass_count,
        "new_fail_this_run": fail_count,
        "last_file": last_file,
        "batch_max": BATCH_MAX,
        "progress_every": PROGRESS_EVERY,
    })

write_progress("RUNNING")
'''
if needle not in s:
    raise SystemExit("PATCH_ABORT progress init target missing")
s = s.replace(needle, repl, 1)

needle = '''    con.commit()
    audited += 1
    if status == "PASS":
        pass_count += 1
    else:
        fail_count += 1

total_audited = con.execute("SELECT COUNT(*) FROM audit_results").fetchone()[0]
'''
repl = '''    con.commit()
    audited += 1
    if status == "PASS":
        pass_count += 1
    else:
        fail_count += 1

    if audited % PROGRESS_EVERY == 0:
        write_progress("RUNNING")

    if audited >= BATCH_MAX:
        break

total_audited = con.execute("SELECT COUNT(*) FROM audit_results").fetchone()[0]
'''
if needle not in s:
    raise SystemExit("PATCH_ABORT batch target missing")
s = s.replace(needle, repl, 1)

needle = '''state = {
    "schema_version": 1,
    "status": "PASS" if total_fail == 0 else "FAIL",
'''
repl = '''remaining_unaudited = 0
for mp in manifests:
    try:
        m = json.loads(mp.read_text())
    except Exception:
        continue
    if m.get("status") != "COMPLETE":
        continue
    expected = str(m.get("sha256") or "")
    p = mp.parent / "klines.parquet"
    if not expected or not p.exists():
        continue
    rel = str(p.relative_to(ROOT))
    row = con.execute(
        "SELECT 1 FROM audit_results WHERE file=? AND expected_sha256=?",
        (rel, expected),
    ).fetchone()
    if row is None:
        remaining_unaudited += 1

state = {
    "schema_version": 2,
    "status": "FAIL" if total_fail else ("RUNNING" if remaining_unaudited else "PASS"),
'''
if needle not in s:
    raise SystemExit("PATCH_ABORT final state target missing")
s = s.replace(needle, repl, 1)

needle = '''    "audited_versions_total": total_audited,
    "pass_total": total_pass,
    "fail_total": total_fail,
'''
repl = '''    "audited_versions_total": total_audited,
    "pass_total": total_pass,
    "fail_total": total_fail,
    "remaining_unaudited": remaining_unaudited,
    "batch_max": BATCH_MAX,
'''
if needle not in s:
    raise SystemExit("PATCH_ABORT final counters target missing")
s = s.replace(needle, repl, 1)

if s == orig:
    raise SystemExit("PATCH_ABORT no_change")

p.write_text(s)
print("PATCH_APPLIED=YES")
PY

"$PY" -m py_compile "$APP"
echo "PY_COMPILE=PASS"

systemctl start --no-block bintrbot-phase1a-audit.service
sleep 3

echo '========== AUDIT PROGRESS =========='
cat "$ROOT/state/phase1a_kline_audit.json" 2>/dev/null || true

echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-phase1a-audit.service || true
systemctl is-active bintrbot-phase1a-audit.timer || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-collector.service || true

echo
echo "BACKUP=$BACKUP"
echo "PHASE1A_PROGRESS_PATCH=PASS"
