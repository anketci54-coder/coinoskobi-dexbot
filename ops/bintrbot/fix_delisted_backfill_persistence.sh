#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
UNIT=/etc/systemd/system/bintrbot-backfill-delisted-klines.service

cat > "$UNIT" <<'UNIT'
[Unit]
Description=BintrBot Historical Delisted TRY 1m Kline Backfill
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/bintrbot
ExecStart=/root/bintrbot/.venv/bin/python /root/bintrbot/app/backfill_delisted_klines.py
User=root
Nice=19
IOSchedulingClass=idle
Restart=on-failure
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable bintrbot-backfill-delisted-klines.service

"$PY" - <<'PY'
from pathlib import Path
import json, os, time

root=Path("/root/bintrbot")
hist=root/"state/phase0a_historical_universe.json"
bf=root/"state/backfill_delisted_klines.json"

h=json.loads(hist.read_text())
b=json.loads(bf.read_text()) if bf.exists() else {}
overlap=sorted(b.get("current_universe_overlap_excluded") or [])

h["current_universe_overlap_symbols"]=overlap
h["market_lifecycle_episode_resolution_required"]=bool(overlap)
h["market_lifecycle_episode_note"]=(
    "A symbol present in both delisted evidence and the current universe may represent "
    "delist/relist or another lifecycle transition. Do not model it as one uninterrupted "
    "trading interval. Resolve LISTED_AT/TRADING_STARTED_AT/TRADING_ENDED_AT episodes before point-in-time replay."
)
h["updated_at_ms"]=time.time_ns()//1_000_000

tmp=hist.with_suffix(".json.tmp")
tmp.write_text(json.dumps(h,ensure_ascii=False,indent=2,sort_keys=True))
os.replace(tmp,h)

print("OVERLAP_SYMBOLS=", ",".join(overlap) if overlap else "NONE")
print("LIFECYCLE_EPISODE_RESOLUTION_REQUIRED=", bool(overlap))
PY

echo
echo '========== PERSISTENCE =========='
systemctl is-enabled bintrbot-backfill-delisted-klines.service
systemctl is-active bintrbot-backfill-delisted-klines.service

echo
echo '========== DELISTED BACKFILL =========='
/root/bintrbot/delisted-history-status.sh | head -35

echo
echo '========== PHASE 0 GATE =========='
/root/bintrbot/phase0-status.sh | head -25

echo
echo "DELISTED_BACKFILL_PERSISTENCE_FIX=PASS"
