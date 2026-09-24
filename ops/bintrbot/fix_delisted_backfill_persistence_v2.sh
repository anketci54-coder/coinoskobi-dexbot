#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
UNIT=/etc/systemd/system/bintrbot-backfill-delisted-klines.service

# Ensure persistence remains configured.
if ! grep -q '^WantedBy=multi-user.target$' "$UNIT"; then
  cat >> "$UNIT" <<'UNIT'

[Install]
WantedBy=multi-user.target
UNIT
fi

systemctl daemon-reload
systemctl enable bintrbot-backfill-delisted-klines.service >/dev/null

"$PY" - <<'PY'
from pathlib import Path
import json, os, time

root = Path("/root/bintrbot")
hist_path = root / "state/phase0a_historical_universe.json"
bf_path = root / "state/backfill_delisted_klines.json"

hist = json.loads(hist_path.read_text())
bf = json.loads(bf_path.read_text()) if bf_path.exists() else {}

overlap = sorted(bf.get("current_universe_overlap_excluded") or [])

hist["current_universe_overlap_symbols"] = overlap
hist["market_lifecycle_episode_resolution_required"] = bool(overlap)
hist["market_lifecycle_episode_note"] = (
    "A symbol present in both delisted evidence and the current universe may represent "
    "delist/relist or another lifecycle transition. Do not model it as one uninterrupted "
    "trading interval. Resolve LISTED_AT/TRADING_STARTED_AT/TRADING_ENDED_AT episodes "
    "before point-in-time replay."
)
hist["updated_at_ms"] = time.time_ns() // 1_000_000

tmp = hist_path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(hist, ensure_ascii=False, indent=2, sort_keys=True))
os.replace(tmp, hist_path)

print("OVERLAP_SYMBOLS=", ",".join(overlap) if overlap else "NONE")
print("LIFECYCLE_EPISODE_RESOLUTION_REQUIRED=", bool(overlap))
PY

echo
echo '========== PERSISTENCE =========='
systemctl is-enabled bintrbot-backfill-delisted-klines.service
systemctl is-active bintrbot-backfill-delisted-klines.service

echo
echo '========== DELISTED BACKFILL =========='
cat "$ROOT/state/backfill_delisted_klines.json" 2>/dev/null || true

echo
echo '========== MAIN SERVICES =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-phase0c-observer.timer || true

echo
echo "DELISTED_BACKFILL_PERSISTENCE_FIX_V2=PASS"
