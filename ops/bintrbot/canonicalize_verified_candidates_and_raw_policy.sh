#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"
HIST="$ROOT/state/phase0a_historical_universe.json"
TRANS="$ROOT/state/phase0a_transition_universe.json"
DISC="$ROOT/state/phase0a_unknown_historical_try_discovery.json"
POLICY="$ROOT/state/phase0a_raw_source_semantics.json"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

for f in "$HIST" "$TRANS" "$DISC"; do
  [ -f "$f" ] && cp -a "$f" "$f.pre_verified_candidates.$TS.bak"
done

"$PY" - "$HIST" "$TRANS" "$DISC" "$POLICY" <<'PY'
from pathlib import Path
import json, os, sys, time

hist_p, trans_p, disc_p, policy_p = map(Path, sys.argv[1:])

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

hist = load(hist_p, {})
hrows = hist.setdefault("confirmed_delisted_try_seed", [])
hby = {r.get("symbol"): r for r in hrows if isinstance(r, dict)}

busd = {
    "symbol": "BUSD_TRY",
    "announced_date": "2023-12-04",
    "delisted_local": "2023-12-08 16:30",
    "source": "BINANCE_TR_OFFICIAL",
    "source_url": "https://www.binance.tr/tr/blog/Announcements/b2483deacd3d4e5c814ffe8cac647c7a",
    "reason": "Paxos stopped issuing new BUSD; Binance TR ended support for BUSD products.",
    "mechanism": "BUSD/TRY was removed and trading stopped; later remaining BUSD balances were converted 1:1 to FDUSD under the announced support wind-down.",
    "result": "BUSD/TRY is a verified historical Binance TR market ending at the stated delisting boundary.",
    "trading_start_local": None,
    "trading_start_status": "UNKNOWN_NOT_YET_VERIFIED",
    "membership_evidence_status": "END_BOUNDARY_VERIFIED_START_PENDING"
}
if busd["symbol"] in hby:
    hby[busd["symbol"]].update(busd)
else:
    hrows.append(busd)

hrows.sort(key=lambda r: r.get("symbol",""))
hist["confirmed_delisted_try_seed"] = hrows
hist["confirmed_delisted_try_seed_count"] = len(hrows)
hist["seed_is_complete"] = False
hist["status"] = "DISCOVERY_REQUIRED"
hist["survivorship_bias_resolved"] = False
hist["venue_window_policy"] = "SILVER_BACKTEST_REQUIRES_VERIFIED_LISTING_START_AND_END"
hist["updated_at_ms"] = time.time_ns() // 1_000_000
atomic(hist_p, hist)

trans = load(trans_p, {})
trows = trans.setdefault("transitions", [])
tby = {r.get("old_symbol"): r for r in trows if isinstance(r, dict)}

verified = [
    {
        "old_symbol": "TOMO_TRY",
        "new_symbol": "VIC_TRY",
        "old_trading_start_local": "2023-09-07 11:00",
        "old_trading_start_status": "VERIFIED",
        "trading_end_local": "2023-11-20 06:00",
        "new_trading_start_local": "2023-11-24 11:00",
        "transition_type": "TOKEN_SWAP_RENAME",
        "swap_note": "1 TOMO = 1 VIC",
        "reason": "TomoChain was renamed to Viction.",
        "mechanism": "TOMO/TRY was closed; TOMO tokens assumed VIC ticker at 1:1; VIC/TRY opened after the transition.",
        "result": "One verified Binance TR market episode ends and a successor VIC/TRY episode begins.",
        "economic_continuity": "RENAME_SWAP_CONTINUITY_1_TO_1",
        "price_series_continuity": "EPISODE_SPLIT_REQUIRED",
        "source": "BINANCE_TR_OFFICIAL",
        "source_url": "https://www.binance.tr/tr/blog/announcements/binance-tr%2C-tomochain%27in-%28tomo%29-viction-%28vic%29-olarak-yeniden-adland%C4%B1r%C4%B1lmas%C4%B1n%C4%B1-destekleyecek-9993a7f4b63147dbaebbf0751dcc3315",
        "listing_source_url": "https://www.binance.tr/blog/Geli%C5%9Fmeler/a172f99c748541b4a5a14b9a0225d82f"
    },
    {
        "old_symbol": "EOS_TRY",
        "new_symbol": "A_TRY",
        "old_trading_start_local": None,
        "old_trading_start_status": "UNKNOWN_NOT_YET_VERIFIED",
        "trading_end_local": "2025-05-26 06:00",
        "new_trading_start_local": "2025-05-28 11:00",
        "transition_type": "TOKEN_SWAP_RENAME",
        "swap_note": "1 EOS = 1 A",
        "reason": "EOS token swap and rebranding to Vaulta (A).",
        "mechanism": "EOS/TRY was removed; EOS tokens were swapped 1:1 to A; A/TRY opened after the transition.",
        "result": "EOS/TRY is a verified historical Binance TR episode ending in the Vaulta transition; exact original listing start remains unresolved.",
        "economic_continuity": "TOKEN_SWAP_REBRAND_CONTINUITY_1_TO_1",
        "price_series_continuity": "EPISODE_SPLIT_REQUIRED",
        "source": "BINANCE_TR_OFFICIAL",
        "source_url": "https://www.binance.tr/blog/announcements/binance-tr-eos-eos-token-takas%C4%B1n%C4%B1-ve-vaulta-a-olarak-yeniden-adland%C4%B1rma-plan%C4%B1n%C4%B1-destekleyecek-1246"
    }
]

for row in verified:
    if row["old_symbol"] in tby:
        tby[row["old_symbol"]].update(row)
    else:
        trows.append(row)
        tby[row["old_symbol"]] = row

trows.sort(key=lambda r:r.get("old_symbol",""))
trans["transitions"] = trows
trans["verified_seed_count"] = len(trows)
trans["seed_is_complete"] = False
trans["venue_window_policy"] = "SILVER_BACKTEST_REQUIRES_VERIFIED_OLD_MARKET_START_AND_END"
trans["updated_at_ms"] = time.time_ns() // 1_000_000
atomic(trans_p, trans)

disc = load(disc_p, {})
found = [r for r in disc.get("found",[]) if isinstance(r,dict)]
verified_syms = {"BUSD_TRY","TOMO_TRY","EOS_TRY"}
remaining = [r.get("symbol") for r in found if r.get("symbol") not in verified_syms]
disc["officially_resolved_candidates"] = {
    "BUSD_TRY": "VERIFIED_DELISTED_BINANCE_TR_MARKET",
    "TOMO_TRY": "VERIFIED_BINANCE_TR_TOKEN_TRANSITION",
    "EOS_TRY": "VERIFIED_BINANCE_TR_TOKEN_TRANSITION",
}
disc["candidate_symbols_pending_official_evidence"] = remaining
disc["candidate_only_symbols_pending_count"] = len(remaining)
disc["candidate_resolution_note"] = (
    "BTT_TRY, FIS_TRY, ZAMA_TRY and 币安人生_TRY remain non-canonical until "
    "Binance TR first-party venue membership evidence is found."
)
disc["updated_at_ms"] = time.time_ns() // 1_000_000
atomic(disc_p, disc)

policy = {
    "schema_version": 1,
    "status": "ENFORCED",
    "recorded_at_ms": time.time_ns() // 1_000_000,
    "bronze_semantics": "RAW_MARKET_DATA_SOURCE_SUPERSET",
    "important_observation": (
        "The official symbolType=1 kline endpoint can return candles outside the "
        "verified Binance TR local venue membership window. Therefore raw candle "
        "availability is not equivalent to local executability."
    ),
    "bronze_rewrite_required": False,
    "bronze_delete_required": False,
    "silver_membership_mask_required": True,
    "backtest_membership_mask_required": True,
    "eligibility_rule": "VERIFIED_LISTING_START <= EVENT_TIME < VERIFIED_DELIST_OR_TRANSITION_END",
    "unknown_start_policy": "FAIL_CLOSED_FOR_SILVER_AND_BACKTEST",
    "unknown_end_policy": "CURRENT_OFFICIAL_MEMBERSHIP_MAY_DEFINE_OPEN_ENDED_ACTIVE_EPISODE",
    "current_membership_authority": "https://www.binance.tr/open/v1/common/symbols",
    "historical_membership_authority": "BINANCE_TR_FIRST_PARTY_ANNOUNCEMENTS_OR_RECORDS",
    "raw_kline_source_type_1": "https://api.binance.me/api/v1/klines",
    "raw_kline_source_type_3": "https://cloudme-tr.2meta.app/api/v1/klines",
    "forbidden_inferences": [
        "KLINE_ACCESSIBLE => BINANCE_TR_LISTED",
        "FIRST_KLINE => BINANCE_TR_LISTING_START",
        "LAST_KLINE => BINANCE_TR_DELIST_TIME"
    ],
    "resolved_candidate_count": 3,
    "pending_candidate_count": len(remaining),
    "pending_candidates": remaining,
}
atomic(policy_p, policy)

print(json.dumps({
    "DELISTED_SEED_TOTAL": len(hrows),
    "TRANSITION_SEED_TOTAL": len(trows),
    "RESOLVED_CANDIDATES": ["BUSD_TRY","TOMO_TRY","EOS_TRY"],
    "PENDING_CANDIDATES": remaining,
    "TOMO_WINDOW": "2023-09-07 11:00 <= t < 2023-11-20 06:00 Europe/Istanbul",
    "EOS_START": "UNKNOWN_NOT_YET_VERIFIED",
    "BUSD_START": "UNKNOWN_NOT_YET_VERIFIED",
    "BRONZE_REWRITE_REQUIRED": False,
    "SILVER_MEMBERSHIP_MASK_REQUIRED": True,
    "UNKNOWN_START_POLICY": "FAIL_CLOSED",
}, ensure_ascii=False, indent=2))
PY

echo
echo '========== RAW SOURCE SEMANTICS =========='
cat "$POLICY"

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-collector.service || true
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-backfill-delisted-klines.service || true
systemctl is-active bintrbot-backfill-transition-klines.timer || true

echo
echo "PHASE0A_VERIFIED_CANDIDATES_AND_RAW_POLICY=PASS"
