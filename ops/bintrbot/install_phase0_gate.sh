#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/phase0_gate.py" <<'PY'
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/root/bintrbot")

def load(path: str):
    p = ROOT / path
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

id0 = load("state/phase0a_identity.json")
bf = load("state/backfill_klines.json")
obs = load("state/phase0c_observation.json")
guardian = load("data/quality/guardian.json")
live = load("data/quality/live.json")

checks = []

def add(name, ok, detail):
    checks.append((name, bool(ok), detail))

add(
    "0A_IDENTITY",
    id0.get("status") == "PASS"
    and int(id0.get("current_try_markets") or 0) > 0
    and int(id0.get("duplicate_symbols") or 0) == 0
    and int(id0.get("duplicate_market_ids") or 0) == 0,
    f'status={id0.get("status")} markets={id0.get("current_try_markets")} '
    f'dup_symbols={id0.get("duplicate_symbols")} dup_market_ids={id0.get("duplicate_market_ids")}'
)

add(
    "0B_BACKFILL_COMPLETION",
    bf.get("status") == "COMPLETE" and int(bf.get("jobs_remaining") or 0) == 0,
    f'status={bf.get("status")} jobs_remaining={bf.get("jobs_remaining")} '
    f'errors={len(bf.get("errors") or {})}'
)

add(
    "0C_TECHNICAL",
    obs.get("technical_status") == "TECHNICAL_PASS",
    f'technical_status={obs.get("technical_status")}'
)

add(
    "0C_7_DAY_OBSERVATION",
    obs.get("seven_day_time_reached") is True,
    f'status={obs.get("status")} elapsed_days={obs.get("elapsed_days")} '
    f'samples={obs.get("samples")} critical_samples={obs.get("critical_samples")}'
)

add(
    "LIVE_FRESH",
    guardian.get("status") == "PASS" and guardian.get("data_fresh") is True,
    f'guardian={guardian.get("status")} data_fresh={guardian.get("data_fresh")} '
    f'alerts={guardian.get("alerts")}'
)

add(
    "LIVE_BOOKS_SYNCED",
    int(live.get("symbols") or 0) > 0
    and int(live.get("books_unsynced") or 0) == 0
    and int(live.get("books_synced") or 0) == int(live.get("symbols") or -1),
    f'symbols={live.get("symbols")} synced={live.get("books_synced")} '
    f'unsynced={live.get("books_unsynced")}'
)

add(
    "APP_QUEUE_DROPS",
    live.get("app_queue_drops_total") == 0,
    f'app_queue_drops_total={live.get("app_queue_drops_total")} '
    f'backpressure={live.get("writer_backpressure_events")}'
)

add(
    "SEALED_MANIFEST_INTEGRITY",
    guardian.get("sealed_manifest_mismatches") == [],
    f'mismatches={guardian.get("sealed_manifest_mismatches")}'
)

print("========== PHASE 0 EXIT GATE ==========")
for name, ok, detail in checks:
    print(f'{"PASS" if ok else "PENDING"} {name} :: {detail}')

blocking = [name for name, ok, _ in checks if not ok]

print()
print("========== CLOSURE ==========")
if blocking:
    print("PHASE0_STATUS=OPEN")
    print("BLOCKERS=" + ",".join(blocking))
else:
    print("PHASE0_STATUS=READY_FOR_PRE_CLOSE_CLEANUP")
    print("BLOCKERS=NONE")

print("PRE_CLOSE_CLEANUP_REQUIRED=true")
print("PRE_CLOSE_CLEANUP_SCOPE=unused_old_data,obsolete_scripts,temporary_backups,caches")
print("CLEANUP_RULE=inventory_first_then_delete_only_verified_unreferenced_files")
PY

cat > "$ROOT/phase0-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
/root/bintrbot/.venv/bin/python /root/bintrbot/app/phase0_gate.py
echo
echo '========== DISK =========='
df -h /
echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-live-guardian.timer || true
systemctl is-active bintrbot-phase0c-observer.timer || true
SH

chmod +x "$ROOT/phase0-status.sh"
"$ROOT/phase0-status.sh"
