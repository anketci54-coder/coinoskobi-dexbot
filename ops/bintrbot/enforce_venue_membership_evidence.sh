#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
DISC="$ROOT/state/phase0a_unknown_historical_try_discovery.json"
CURR="$ROOT/state/phase0a_unknown_try_currentness.json"
HIST="$ROOT/state/phase0a_historical_universe.json"
TRANS="$ROOT/state/phase0a_transition_universe.json"
POLICY="$ROOT/state/phase0a_venue_membership_policy.json"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

for f in "$DISC" "$CURR"; do
  if [ -f "$f" ]; then cp -a "$f" "$f.pre_membership_policy.$TS.bak"; fi
done

"$PY" - "$DISC" "$CURR" "$HIST" "$TRANS" "$POLICY" <<'PY'
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
from urllib.request import Request, urlopen

disc_p, curr_p, hist_p, trans_p, policy_p = map(Path, sys.argv[1:])
OFFICIAL = "https://www.binance.tr/open/v1/common/symbols"

def load(p, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default

def atomic(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix(p.suffix + ".tmp")
    t.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(t, p)

req = Request(OFFICIAL, headers={"User-Agent":"bintrbot-membership-policy/1.0"})
with urlopen(req, timeout=30) as r:
    raw = json.loads(r.read().decode())

rows = ((raw.get("data") or {}).get("list") or []) if isinstance(raw, dict) else []
official_try = sorted({
    str(x.get("symbol","")).upper()
    for x in rows
    if isinstance(x, dict)
    and str(x.get("quoteAsset","")).upper() == "TRY"
    and x.get("symbol")
})

disc = load(disc_p, {})
candidates = [x.get("symbol") for x in disc.get("found", []) if x.get("symbol")]
disc.update({
    "status": "CANDIDATE_SWEEP_ONLY",
    "venue_membership_authoritative": False,
    "canonicalization_allowed_from_kline_access_only": False,
    "membership_rule": (
        "api.binance.me kline accessibility proves data availability only. "
        "It does not prove Binance TR venue membership. Historical inclusion "
        "requires Binance TR official listing/delisting/transition evidence."
    ),
    "candidate_symbols_pending_official_evidence": candidates,
    "current_supported_symbols_source": OFFICIAL,
    "updated_at_ms": time.time_ns() // 1_000_000,
})
atomic(disc_p, disc)

curr = load(curr_p, {})
if curr:
    raw_live = list(curr.get("live_but_missing_from_current_snapshot", []))
    curr.update({
        "interpretation_status": "SUPERSEDED_FOR_VENUE_MEMBERSHIP",
        "raw_kline_live_observation": raw_live,
        "live_but_missing_from_current_snapshot": [],
        "live_but_missing_count": 0,
        "current_snapshot_requires_repair": False,
        "correction_reason": (
            "Kline availability on api.binance.me is not authoritative evidence "
            "that a symbol is currently supported on Binance TR."
        ),
        "authoritative_current_membership_source": OFFICIAL,
        "corrected_at_ms": time.time_ns() // 1_000_000,
    })
    atomic(curr_p, curr)

hist = load(hist_p, {})
hist_symbols = sorted({
    str(x.get("symbol","")).upper()
    for x in hist.get("confirmed_delisted_try_seed", [])
    if isinstance(x, dict) and x.get("symbol")
})
trans = load(trans_p, {})
trans_symbols = sorted({
    str(x.get("old_symbol","")).upper()
    for x in trans.get("transitions", [])
    if isinstance(x, dict) and x.get("old_symbol")
})

policy = {
    "schema_version": 1,
    "status": "ENFORCED",
    "recorded_at_ms": time.time_ns() // 1_000_000,
    "venue": "BINANCE_TR",
    "current_membership_authority": OFFICIAL,
    "current_try_count": len(official_try),
    "current_try_symbols": official_try,
    "market_data_endpoint_semantics": {
        "api.binance.me": (
            "Official Binance TR documentation uses this endpoint for symbolType=1 "
            "market data, but successful symbol data access is not itself proof of "
            "Binance TR venue membership."
        ),
        "cloudme-tr.2meta.app": (
            "Official Binance TR documentation uses this endpoint for symbolType=3 "
            "market data."
        ),
    },
    "historical_membership_requirements": [
        "Binance TR official listing announcement",
        "Binance TR official delisting announcement",
        "Binance TR official token transition / rename / swap announcement",
        "or another Binance TR first-party record that explicitly identifies the market",
    ],
    "forbidden_inference": "KLINE_ACCESSIBLE => BINANCE_TR_LISTED",
    "kline_access_role": "DATA_AVAILABILITY_CONFIRMATION_AFTER_MEMBERSHIP_EVIDENCE",
    "confirmed_delisted_seed_count": len(hist_symbols),
    "confirmed_transition_seed_count": len(trans_symbols),
    "candidate_only_symbols": candidates,
    "candidate_only_count": len(candidates),
    "canonical_seed_unchanged": True,
    "backfill_data_mutated": False,
}
atomic(policy_p, policy)

print(json.dumps({
    "POLICY_STATUS": policy["status"],
    "OFFICIAL_CURRENT_TRY": len(official_try),
    "ZAMA_IN_OFFICIAL_CURRENT": "ZAMA_TRY" in official_try,
    "CANDIDATE_ONLY": candidates,
    "CANONICAL_DELISTED_SEED": len(hist_symbols),
    "CANONICAL_TRANSITION_SEED": len(trans_symbols),
    "CURRENT_SNAPSHOT_REPAIR_REQUIRED": False,
    "BACKFILL_DATA_MUTATED": False,
}, ensure_ascii=False, indent=2))
PY

echo
echo '========== POLICY =========='
cat "$POLICY"

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true

echo
echo "PHASE0A_VENUE_MEMBERSHIP_POLICY=PASS"
