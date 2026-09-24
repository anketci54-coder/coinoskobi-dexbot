#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

"$PY" - <<'PY'
import json
from pathlib import Path

cat=json.loads(Path("/root/bintrbot/data/catalog/dataset_catalog.json").read_text())
hist=json.loads(Path("/root/bintrbot/state/phase0a_historical_universe.json").read_text())
trans=json.loads(Path("/root/bintrbot/state/phase0a_transition_universe.json").read_text())

pending=cat.get("strict_boundary_pending_symbols",[])
h={r.get("symbol"):r for r in hist.get("confirmed_delisted_try_seed",[]) if isinstance(r,dict)}
t={r.get("old_symbol"):r for r in trans.get("transitions",[]) if isinstance(r,dict)}

print("STRICT_READY_SYMBOLS=",len(cat.get("strict_ready_symbols",[])))
print("STRICT_BOUNDARY_PENDING=",len(pending))
print()

for s in pending:
    eps=(cat.get("episode_windows") or {}).get(s) or []
    if s in t:
        r=t[s]
        kind="TRANSITION"
        reason=f"start={r.get('old_trading_start_local')} start_status={r.get('old_trading_start_status')} end={r.get('trading_end_local')}"
    elif s in h:
        r=h[s]
        kind="DELISTED"
        reason=f"start={r.get('trading_start_local')} start_status={r.get('trading_start_status')} end={r.get('delisted_local')}"
    else:
        kind="CURRENT_OR_OTHER"
        reason=f"episodes={eps}"
    print(f"{s} | {kind} | {reason}")

print()
for p in [
    "/root/bintrbot/state/backfill_klines.json",
    "/root/bintrbot/state/backfill_delisted_klines.json",
    "/root/bintrbot/state/backfill_transition_klines.json",
    "/root/bintrbot/state/backfill_uncertain_candidates.json",
]:
    q=Path(p)
    if not q.exists():
        continue
    x=json.loads(q.read_text())
    print(q.name, "status=",x.get("status"),"jobs_remaining=",x.get("jobs_remaining"))
PY

echo
echo "STRICT_PENDING_AUDIT=PASS"
