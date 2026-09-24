#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
OUT="$ROOT/state/phase0a_candidate_membership_evidence.json"
HIST="$ROOT/state/phase0a_historical_universe.json"
GATE="$ROOT/app/phase0_gate.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

[ -f "$GATE" ] && cp -a "$GATE" "$GATE.pre_candidate_gate.$TS.bak"
[ -f "$HIST" ] && cp -a "$HIST" "$HIST.pre_candidate_gate.$TS.bak"

cat > "$OUT" <<'JSON'
{
  "schema_version": 1,
  "status": "PENDING_OFFICIAL_BINANCE_TR_EVIDENCE",
  "policy": "Historical Binance TR venue membership requires Binance TR first-party evidence. Kline accessibility or Binance.com-only evidence is insufficient.",
  "resolved_candidates": {
    "BUSD_TRY": "VERIFIED_DELISTED_BINANCE_TR_MARKET",
    "TOMO_TRY": "VERIFIED_BINANCE_TR_TOKEN_TRANSITION",
    "EOS_TRY": "VERIFIED_BINANCE_TR_TOKEN_TRANSITION"
  },
  "pending_candidates": {
    "BTT_TRY": {
      "status": "QUARANTINED",
      "reason": "Binance.com documents BTT/TRY migration to BTTC/TRY, but no Binance TR first-party record has yet been captured proving the old BTT/TRY venue episode.",
      "noncanonical_evidence": "https://www.binance.com/en-PH/support/announcement/detail/2722e6da4f5141dd9b2fb07b5b1f3f75"
    },
    "FIS_TRY": {
      "status": "QUARANTINED",
      "reason": "Historical kline accessibility observed, but no Binance TR first-party listing/delisting/transition evidence has yet been captured."
    },
    "ZAMA_TRY": {
      "status": "QUARANTINED",
      "reason": "Binance.com announced ZAMA/TRY, but the authoritative current Binance TR common/symbols snapshot does not contain ZAMA_TRY and no Binance TR first-party lifecycle record has yet been captured.",
      "noncanonical_evidence": "https://www.binance.com/en/support/announcement/detail/c411646abd94488bba084537c5563beb"
    },
    "币安人生_TRY": {
      "status": "QUARANTINED",
      "reason": "Binance.com announced 币安人生/TRY, but no Binance TR first-party lifecycle record has yet been captured.",
      "noncanonical_evidence": "https://www.binance.com/en/support/announcement/detail/51881f9d018242ce80bed6ce015de2a7"
    }
  },
  "canonicalization_allowed": false,
  "backfill_allowed_for_pending_candidates": false
}
JSON

"$PY" - "$HIST" <<'PY'
from pathlib import Path
import json, os, sys, time

p=Path(sys.argv[1])
x=json.loads(p.read_text())
x["unresolved_candidate_symbols"]=["BTT_TRY","FIS_TRY","ZAMA_TRY","币安人生_TRY"]
x["unresolved_candidate_count"]=4
x["candidate_membership_evidence_state"]="/root/bintrbot/state/phase0a_candidate_membership_evidence.json"
x["seed_is_complete"]=False
x["survivorship_bias_resolved"]=False
x["status"]="DISCOVERY_REQUIRED"
x["updated_at_ms"]=time.time_ns()//1_000_000
tmp=p.with_suffix(".json.tmp")
tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True))
os.replace(tmp,p)
print("HISTORICAL_UNIVERSE_FAIL_CLOSED=YES")
PY

"$PY" - "$GATE" <<'PY'
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()

if 'candidate0 = load("state/phase0a_candidate_membership_evidence.json")' not in s:
    anchor='hist0 = load("state/phase0a_historical_universe.json")'
    if anchor not in s:
        raise SystemExit("PATCH_ABORT hist0 load missing")
    s=s.replace(anchor, anchor+'\ncandidate0 = load("state/phase0a_candidate_membership_evidence.json")',1)

if '"0A_MEMBERSHIP_EVIDENCE"' not in s:
    anchor='''add(
    "0B_BACKFILL_COMPLETION",
'''
    block='''add(
    "0A_MEMBERSHIP_EVIDENCE",
    candidate0.get("status") == "COMPLETE"
    and len(candidate0.get("pending_candidates") or {}) == 0,
    f'status={candidate0.get("status")} pending_candidates={len(candidate0.get("pending_candidates") or {})}'
)

'''
    if anchor not in s:
        raise SystemExit("PATCH_ABORT 0B anchor missing")
    s=s.replace(anchor,block+anchor,1)

p.write_text(s)
print("PHASE0_GATE_CANDIDATE_EVIDENCE_PATCH=YES")
PY

"$PY" -m py_compile "$GATE"

echo '========== CANDIDATE EVIDENCE =========='
"$PY" - <<'PY'
import json
from pathlib import Path
x=json.loads(Path("/root/bintrbot/state/phase0a_candidate_membership_evidence.json").read_text())
print("STATUS=",x["status"])
print("RESOLVED=",len(x["resolved_candidates"]))
print("PENDING=",len(x["pending_candidates"]))
for s,v in x["pending_candidates"].items():
    print("PENDING",s,v["status"])
PY

echo
echo '========== PHASE 0 GATE =========='
"$ROOT/phase0-status.sh"

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true
echo
echo "PHASE0A_CANDIDATE_MEMBERSHIP_GATE=PASS"
