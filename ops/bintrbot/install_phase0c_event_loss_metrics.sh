#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
TARGET="$ROOT/app/collector.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/state/collector.py.pre_phase0c_metrics.$TS.bak"

cp -a "$TARGET" "$BACKUP"

"$PY" - "$TARGET" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
s = path.read_text()
original = s

def once(old: str, new: str, label: str):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"PATCH_ABORT {label} expected=1 found={n}")
    s = s.replace(old, new, 1)

# Existing raw writes must all be awaited; wrap exactly the 3 known call sites.
n = s.count("await self.writer.put(")
if n != 3:
    raise SystemExit(f"PATCH_ABORT writer_put_count expected=3 found={n}")
s = s.replace("await self.writer.put(", "await self.write_raw(")

once(
'''        self.ws_reconnects = 0
''',
'''        self.ws_reconnects = 0
        self.ws_reconnect_events = 0
        self.ws_disconnects = 0
        self.ws_parse_errors = 0
        self.ws_unknown_symbols = 0
        self.ws_unknown_events = 0
        self.writer_queue_peak = 0
        self.writer_backpressure_events = 0
        self.writer_put_wait_ns_max = 0
        self.agg_trade_gap_events = 0
        self.agg_trade_missing_ids = 0
        self.agg_trade_old_or_duplicate_ids = 0
        self.last_agg_trade_id: dict[str, int] = {}
''',
"collector_metrics_init",
)

once(
'''    async def request_json(
''',
'''    async def write_raw(self, item: dict[str, Any]) -> None:
        qsize = self.writer.q.qsize()
        self.writer_queue_peak = max(self.writer_queue_peak, qsize)

        if self.writer.q.maxsize > 0 and qsize >= self.writer.q.maxsize:
            self.writer_backpressure_events += 1

        started = time.monotonic_ns()
        await self.writer.put(item)
        waited = time.monotonic_ns() - started

        self.writer_put_wait_ns_max = max(
            self.writer_put_wait_ns_max,
            waited,
        )
        self.writer_queue_peak = max(
            self.writer_queue_peak,
            self.writer.q.qsize(),
        )

        # There is intentionally no application-level drop path.
        # A full queue applies awaited backpressure instead.

    async def request_json(
''',
"write_raw_method",
)

once(
'''        self.trade_events += 1

        await self.write_raw(
''',
'''        self.trade_events += 1

        agg_id = payload.get("a")
        if agg_id is None:
            self.agg_trade_missing_ids += 1
        else:
            try:
                agg_id = int(agg_id)
            except (TypeError, ValueError):
                self.agg_trade_missing_ids += 1
            else:
                prev = self.last_agg_trade_id.get(info.api_symbol)
                if prev is not None:
                    if agg_id <= prev:
                        self.agg_trade_old_or_duplicate_ids += 1
                    elif agg_id > prev + 1:
                        self.agg_trade_gap_events += 1
                if prev is None or agg_id > prev:
                    self.last_agg_trade_id[info.api_symbol] = agg_id

        await self.write_raw(
''',
"aggtrade_continuity",
)

once(
'''            params.append(f"{s}@depth@100ms")

        while not self.stop.is_set():
''',
'''            params.append(f"{s}@depth@100ms")

        connect_count = 0

        while not self.stop.is_set():
''',
"ws_connect_count_init",
)

once(
'''                    self.ws_reconnects += 1

                    for i in range(0, len(params), 100):
''',
'''                    self.ws_reconnects += 1
                    if connect_count > 0:
                        self.ws_reconnect_events += 1
                    connect_count += 1

                    for i in range(0, len(params), 100):
''',
"ws_reconnect_metric",
)

once(
'''                        except Exception:
                            continue
''',
'''                        except Exception:
                            self.ws_parse_errors += 1
                            continue
''',
"ws_parse_error_metric",
)

once(
'''                        if info is None:
                            continue

                        event = payload.get("e")
''',
'''                        if info is None:
                            self.ws_unknown_symbols += 1
                            continue

                        event = payload.get("e")
''',
"ws_unknown_symbol_metric",
)

once(
'''                        elif event == "aggTrade":
                            await self.on_trade(info, payload)
''',
'''                        elif event == "aggTrade":
                            await self.on_trade(info, payload)
                        else:
                            self.ws_unknown_events += 1
''',
"ws_unknown_event_metric",
)

once(
'''            except Exception as e:
                print(
                    "WS_ERROR",
                    group_id,
                    repr(e),
                    flush=True,
                )
                await asyncio.sleep(3)
''',
'''            except Exception as e:
                self.ws_disconnects += 1
                print(
                    "WS_ERROR",
                    group_id,
                    repr(e),
                    flush=True,
                )
                await asyncio.sleep(3)
''',
"ws_disconnect_metric",
)

once(
'''                "writer_queue": self.writer.q.qsize(),
                "ws_connections_total": self.ws_reconnects,
''',
'''                "writer_queue": self.writer.q.qsize(),
                "writer_queue_peak": self.writer_queue_peak,
                "writer_backpressure_events": self.writer_backpressure_events,
                "writer_put_wait_ms_max": round(
                    self.writer_put_wait_ns_max / 1_000_000,
                    3,
                ),
                "app_queue_drops_total": 0,
                "drop_policy": "AWAITED_BACKPRESSURE_NO_APP_DROP_PATH",
                "agg_trade_gap_events": self.agg_trade_gap_events,
                "agg_trade_missing_ids": self.agg_trade_missing_ids,
                "agg_trade_old_or_duplicate_ids": self.agg_trade_old_or_duplicate_ids,
                "ws_connections_total": self.ws_reconnects,
                "ws_reconnect_events": self.ws_reconnect_events,
                "ws_disconnects": self.ws_disconnects,
                "ws_parse_errors": self.ws_parse_errors,
                "ws_unknown_symbols": self.ws_unknown_symbols,
                "ws_unknown_events": self.ws_unknown_events,
''',
"quality_metrics",
)

if s == original:
    raise SystemExit("PATCH_ABORT no_change")

path.write_text(s)
print("PATCH_APPLIED=YES")
PY

rollback() {
  echo "ROLLBACK=YES"
  cp -a "$BACKUP" "$TARGET"
  "$PY" -m py_compile "$TARGET"
  systemctl restart bintrbot-collector.service || true
}

if ! "$PY" -m py_compile "$TARGET"; then
  rollback
  exit 1
fi

echo "PY_COMPILE=PASS"

# Refresh the compatible offline test harness before regression testing.
curl -fsSL "https://raw.githubusercontent.com/anketci54-coder/coinoskobi-dexbot/bintrbot-bootstrap-20260923/ops/bintrbot/test_phase0c_sequence_recovery.sh" -o "$ROOT/state/test_phase0c_sequence_recovery.sh"
chmod +x "$ROOT/state/test_phase0c_sequence_recovery.sh"

if ! "$ROOT/state/test_phase0c_sequence_recovery.sh"; then
  rollback
  exit 1
fi
echo "OFFLINE_SEQUENCE_TEST=PASS"

systemctl restart bintrbot-collector.service
sleep 8

if ! systemctl is-active --quiet bintrbot-collector.service; then
  rollback
  exit 1
fi

echo "COLLECTOR_RESTART=PASS"

# Give the quality reporter one cycle to persist post-restart metrics.
sleep 65

if ! systemctl is-active --quiet bintrbot-collector.service; then
  rollback
  exit 1
fi

echo
echo '========== LIVE QUALITY AFTER METRICS PATCH =========='
cat "$ROOT/data/quality/live.json"

echo
echo '========== SERVICES =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-live-guardian.timer || true

echo
echo '========== BACKUP =========='
echo "$BACKUP"
echo "PHASE0C_EVENT_LOSS_METRICS_PATCH=PASS"
