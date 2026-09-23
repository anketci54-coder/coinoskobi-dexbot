#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
APP="$ROOT/app/phase1a_kline_audit.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/state/phase1a_kline_audit.py.pre_conclose_fix.$TS.bak"

systemctl stop bintrbot-phase1a-audit.service 2>/dev/null || true
cp -a "$APP" "$BACKUP"

"$PY" - "$APP" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()
orig = s

old = '''con.close()

remaining_unaudited = 0
'''
new = '''remaining_unaudited = 0
'''
if old not in s:
    raise SystemExit("PATCH_ABORT early_con_close_target_missing")
s = s.replace(old, new, 1)

needle = '''state = {
    "schema_version": 2,
'''
replacement = '''con.close()

state = {
    "schema_version": 2,
'''
if needle not in s:
    raise SystemExit("PATCH_ABORT final_state_target_missing")
s = s.replace(needle, replacement, 1)

if s == orig:
    raise SystemExit("PATCH_ABORT no_change")

p.write_text(s)
print("PATCH_APPLIED=YES")
PY

"$PY" -m py_compile "$APP"
echo "PY_COMPILE=PASS"

systemctl reset-failed bintrbot-phase1a-audit.service || true
systemctl start --no-block bintrbot-phase1a-audit.service
sleep 5

echo '========== AUDIT PROGRESS =========='
cat "$ROOT/state/phase1a_kline_audit.json" 2>/dev/null || true

echo
echo '========== AUDIT SERVICE =========='
systemctl is-active bintrbot-phase1a-audit.service || true
systemctl is-failed bintrbot-phase1a-audit.service || true

echo
echo '========== DATA SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-collector.service || true

echo
echo "BACKUP=$BACKUP"
echo "PHASE1A_CON_CLOSE_FIX=PASS"
