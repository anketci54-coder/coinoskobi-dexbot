#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

mkdir -p "$ROOT/app" "$ROOT/state" "$ROOT/data/quality/history"

cat > "$ROOT/app/phase0c_observer.py" <<'PY'
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/bintrbot")
LIVE = ROOT / "data/quality/live.json"
GUARDIAN = ROOT / "data/quality/guardian.json"
STATE = ROOT / "state/phase0c_observation.json"
HISTORY = ROOT / "data/quality/history"

SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

def now_ms():
    return time.time_ns() // 1_000_000

def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()

def load(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def atomic(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

now = now_ms()
state = load(STATE)
start = int(state.get("observation_started_at_ms") or now)

live = load(LIVE)
guardian = load(GUARDIAN)

record = {
    "sample_at_ms": now,
    "sample_at_utc": iso(now),
    "live_timestamp_ms": live.get("timestamp_ms"),
    "symbols": live.get("symbols"),
    "books_synced": live.get("books_synced"),
    "books_unsynced": live.get("books_unsynced"),
    "sequence_gaps_total": live.get("sequence_gaps_total"),
    "depth_events": live.get("depth_events"),
    "agg_trade_events": live.get("agg_trade_events"),
    "writer_queue": live.get("writer_queue"),
    "writer_queue_peak": live.get("writer_queue_peak"),
    "writer_backpressure_events": live.get("writer_backpressure_events"),
    "app_queue_drops_total": live.get("app_queue_drops_total"),
    "agg_trade_gap_events": live.get("agg_trade_gap_events"),
    "agg_trade_missing_ids": live.get("agg_trade_missing_ids"),
    "agg_trade_old_or_duplicate_ids": live.get("agg_trade_old_or_duplicate_ids"),
    "ws_connections_total": live.get("ws_connections_total"),
    "ws_reconnect_events": live.get("ws_reconnect_events"),
    "ws_disconnects": live.get("ws_disconnects"),
    "ws_parse_errors": live.get("ws_parse_errors"),
    "guardian_status": guardian.get("status"),
    "data_fresh": guardian.get("data_fresh"),
    "guardian_alerts": guardian.get("alerts") or [],
    "sealed_manifest_mismatches": guardian.get("sealed_manifest_mismatches") or [],
    "disk_free_gib": guardian.get("disk_free_gib"),
}

day = datetime.fromtimestamp(now / 1000, timezone.utc).strftime("%Y-%m-%d")
out = HISTORY / f"phase0c-{day}.jsonl"
with out.open("a", encoding="utf-8") as f:
    f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    f.flush()
    os.fsync(f.fileno())

samples = int(state.get("samples") or 0) + 1
elapsed = max(0, now - start)

critical_samples = int(state.get("critical_samples") or 0)
if (
    guardian.get("status") != "PASS"
    or guardian.get("data_fresh") is not True
    or (live.get("books_unsynced") not in (0, None))
    or (live.get("app_queue_drops_total") not in (0, None))
):
    critical_samples += 1

new_state = {
    "schema_version": 1,
    "status": "OBSERVING" if elapsed < SEVEN_DAYS_MS else "SEVEN_DAY_WINDOW_REACHED",
    "technical_status": "TECHNICAL_PASS",
    "observation_started_at_ms": start,
    "observation_started_at_utc": iso(start),
    "last_sample_at_ms": now,
    "last_sample_at_utc": iso(now),
    "elapsed_ms": elapsed,
    "elapsed_days": round(elapsed / 86_400_000, 6),
    "samples": samples,
    "critical_samples": critical_samples,
    "seven_day_window_ms": SEVEN_DAYS_MS,
    "seven_day_time_reached": elapsed >= SEVEN_DAYS_MS,
    "history_dir": str(HISTORY.relative_to(ROOT)),
}
atomic(STATE, new_state)
print(json.dumps(new_state, ensure_ascii=False, indent=2))
PY

cat > /etc/systemd/system/bintrbot-phase0c-observer.service <<'UNIT'
[Unit]
Description=BintrBot Phase 0C Observation Recorder
After=bintrbot-live-guardian.service

[Service]
Type=oneshot
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/phase0c_observer.py
User=root
Nice=15
IOSchedulingClass=best-effort
IOSchedulingPriority=7
UNIT

cat > /etc/systemd/system/bintrbot-phase0c-observer.timer <<'UNIT'
[Unit]
Description=Record BintrBot Phase 0C Health Every Minute

[Timer]
OnBootSec=3min
OnUnitActiveSec=1min
AccuracySec=10s
Persistent=true
Unit=bintrbot-phase0c-observer.service

[Install]
WantedBy=timers.target
UNIT

cat > "$ROOT/phase0c-observation-status.sh" <<'SH'
#!/usr/bin/env bash
set -u
echo '========== PHASE 0C OBSERVATION =========='
cat /root/bintrbot/state/phase0c_observation.json 2>/dev/null || echo 'state missing'
echo
echo '========== HISTORY =========='
du -sh /root/bintrbot/data/quality/history 2>/dev/null || true
find /root/bintrbot/data/quality/history -type f -name 'phase0c-*.jsonl' 2>/dev/null | sort | tail -10
echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-live-guardian.timer || true
systemctl is-active bintrbot-phase0c-observer.timer || true
SH

chmod +x "$ROOT/phase0c-observation-status.sh"

systemctl daemon-reload
systemctl enable --now bintrbot-phase0c-observer.timer
systemctl start bintrbot-phase0c-observer.service
sleep 1

"$ROOT/phase0c-observation-status.sh"
