#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/state/phase0a_historical_universe.json" <<'JSON'
{
  "schema_version": 1,
  "status": "DISCOVERY_REQUIRED",
  "survivorship_bias_resolved": false,
  "scope": "BINANCE_TR_TRY_HISTORICAL_MARKETS",
  "reason": "Current supported-symbol endpoint is a present-time snapshot and cannot represent delisted historical TRY markets.",
  "confirmed_delisted_try_seed": [
    {"symbol":"WAVES_TRY","delisted_local":"2024-06-17 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"JOE_TRY","delisted_local":"2024-08-23 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"BAND_TRY","delisted_local":"2024-09-13 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"STMX_TRY","delisted_local":"2025-02-24 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"COMBO_TRY","delisted_local":"2025-03-28 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"TROY_TRY","delisted_local":"2025-04-16 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"BSW_TRY","delisted_local":"2025-07-04 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"LEVER_TRY","delisted_local":"2025-07-04 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"XVS_TRY","delisted_local":"2025-08-01 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"YGG_TRY","delisted_local":"2025-08-01 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"BAKE_TRY","delisted_local":"2025-09-17 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"SLF_TRY","delisted_local":"2025-09-17 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"VTHO_TRY","delisted_local":"2025-12-26 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"ACA_TRY","delisted_local":"2026-02-13 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"LRC_TRY","delisted_local":"2026-04-01 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"NTRN_TRY","delisted_local":"2026-04-01 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"RDNT_TRY","delisted_local":"2026-04-01 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"SXP_TRY","delisted_local":"2026-04-01 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"DENT_TRY","delisted_local":"2026-04-28 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"TRU_TRY","delisted_local":"2026-04-28 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"PHB_TRY","delisted_local":"2026-05-27 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"COS_TRY","delisted_local":"2026-06-19 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"D_TRY","delisted_local":"2026-06-19 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"HIGH_TRY","delisted_local":"2026-06-19 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"MBOX_TRY","delisted_local":"2026-06-19 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"NFP_TRY","delisted_local":"2026-07-10 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"MOVE_TRY","delisted_local":"2026-07-31 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"STORJ_TRY","delisted_local":"2026-07-31 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"BTTC_TRY","delisted_local":"2026-08-14 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"ACX_TRY","delisted_local":"2026-08-17 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"VANRY_TRY","delisted_local":"2026-08-17 06:00","source":"BINANCE_TR_OFFICIAL"},
    {"symbol":"VIC_TRY","delisted_local":"2026-08-17 06:00","source":"BINANCE_TR_OFFICIAL"}
  ],
  "seed_is_complete": false,
  "next_step": "Build exhaustive listing/delisting history and attempt historical 1m recovery for delisted TRY markets before survivorship-bias gate can pass."
}
JSON

"$PY" - "$ROOT/app/phase0_gate.py" <<'PY'
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()

old='''id0 = load("state/phase0a_identity.json")
bf = load("state/backfill_klines.json")
'''
new='''id0 = load("state/phase0a_identity.json")
hist0 = load("state/phase0a_historical_universe.json")
bf = load("state/backfill_klines.json")
'''
if old not in s:
    raise SystemExit("PATCH_ABORT load target missing")
s=s.replace(old,new,1)

old='''add(
    "0B_BACKFILL_COMPLETION",
'''
new='''add(
    "0A_HISTORICAL_UNIVERSE",
    hist0.get("status") == "COMPLETE"
    and hist0.get("survivorship_bias_resolved") is True,
    f'status={hist0.get("status")} survivorship_bias_resolved={hist0.get("survivorship_bias_resolved")} '
    f'confirmed_delisted_seed={len(hist0.get("confirmed_delisted_try_seed") or [])}'
)

add(
    "0B_BACKFILL_COMPLETION",
'''
if old not in s:
    raise SystemExit("PATCH_ABORT gate target missing")
s=s.replace(old,new,1)

p.write_text(s)
print("PHASE0_GATE_PATCHED=YES")
PY

"$PY" -m py_compile "$ROOT/app/phase0_gate.py"

echo '========== HISTORICAL UNIVERSE SEED =========='
"$PY" - <<'PY'
import json
from pathlib import Path
p=Path("/root/bintrbot/state/phase0a_historical_universe.json")
x=json.loads(p.read_text())
print("STATUS=",x["status"])
print("CONFIRMED_DELISTED_TRY_SEED=",len(x["confirmed_delisted_try_seed"]))
print("SEED_IS_COMPLETE=",x["seed_is_complete"])
print("SURVIVORSHIP_BIAS_RESOLVED=",x["survivorship_bias_resolved"])
PY

echo
/root/bintrbot/phase0-status.sh
