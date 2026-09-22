#!/usr/bin/env python3
"""Fast read-only causal WARM/HOT replay dataset builder.

Decision features use only observations available at or before decision_time.
Future fields are evaluation-only and must never be consumed by a decision policy.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import statistics
import time
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HORIZONS = {
    "30m": 30 * 60,
    "1h": 60 * 60,
    "3h": 3 * 60 * 60,
    "6h": 6 * 60 * 60,
    "24h": 24 * 60 * 60,
}


def parse_time(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    text = str(value).strip()
    if not text:
        return None
    try:
        value = float(text)
        return value if math.isfinite(value) else None
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def iso_utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def pct(new: float, old: float) -> float | None:
    if old <= 0 or not math.isfinite(old) or not math.isfinite(new):
        return None
    return (new / old - 1.0) * 100.0


def median(values):
    clean = [
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    ]
    return statistics.median(clean) if clean else None


def latest_at_or_before(rows, target: float, times=None):
    if not rows:
        return None
    if times is None:
        times = [row["t"] for row in rows]
    index = bisect_right(times, target) - 1
    return None if index < 0 else rows[index]


def first_at_or_after(rows, target: float, max_gap: float, times=None):
    if not rows:
        return None
    if times is None:
        times = [row["t"] for row in rows]
    index = bisect_left(times, target)
    if index >= len(rows):
        return None
    row = rows[index]
    return row if row["t"] - target <= max_gap else None


def window(rows, start: float, end: float, times=None):
    if not rows:
        return []
    if times is None:
        times = [row["t"] for row in rows]
    left = bisect_left(times, start)
    right = bisect_right(times, end)
    return rows[left:right]


def latest_state_at_or_before(rows, target: float, times=None):
    row = latest_at_or_before(rows, target, times)
    return None if row is None else row["next_state"]


def first_hot_after(rows, start: float, end: float, times=None):
    if not rows:
        return None
    if times is None:
        times = [row["t"] for row in rows]
    left = bisect_right(times, start)
    right = bisect_right(times, end)
    for row in rows[left:right]:
        if row["next_state"] == "HOT":
            return row["t"]
    return None


def cohort_summary(rows):
    return {
        "count": len(rows),
        "median_pre_decision_return_pct": median(
            row["pre_decision_return_pct"] for row in rows
        ),
        "median_pre_decision_mfe_pct": median(
            row["pre_decision_mfe_pct"] for row in rows
        ),
        "median_pre_decision_mae_pct": median(
            row["pre_decision_mae_pct"] for row in rows
        ),
        "median_eval_return_1h_pct": median(
            row["eval_return_1h_pct"] for row in rows
        ),
        "median_eval_return_6h_pct": median(
            row["eval_return_6h_pct"] for row in rows
        ),
        "median_eval_return_24h_pct": median(
            row["eval_return_24h_pct"] for row in rows
        ),
        "median_eval_mfe_1h_pct": median(
            row["eval_mfe_1h_pct"] for row in rows
        ),
        "median_eval_mfe_6h_pct": median(
            row["eval_mfe_6h_pct"] for row in rows
        ),
        "median_eval_mfe_24h_pct": median(
            row["eval_mfe_24h_pct"] for row in rows
        ),
        "median_eval_mae_24h_pct": median(
            row["eval_mae_24h_pct"] for row in rows
        ),
        "median_time_to_peak_24h_seconds": median(
            row["eval_time_to_peak_24h_seconds"] for row in rows
        ),
        "median_first_below_decision_seconds": median(
            row["eval_first_below_decision_seconds"] for row in rows
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/cache/cache.db")
    parser.add_argument("--decision-delay-seconds", type=int, default=600)
    parser.add_argument(
        "--out-dir",
        default="/tmp/coinoskobi-opportunity-replay-v1",
    )
    args = parser.parse_args()

    if args.decision_delay_seconds <= 0:
        raise SystemExit("decision delay must be positive")

    started = time.monotonic()
    db_path = Path(args.db).resolve()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"REPLAY_START delay={args.decision_delay_seconds}s db={db_path}",
        flush=True,
    )

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")

    required = {
        "universe_pool_registry",
        "universe_market_observation_v1",
        "universe_seismic_evaluation_v1",
    }
    tables = {
        row["name"]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    missing = sorted(required - tables)
    if missing:
        raise SystemExit("missing tables: " + ", ".join(missing))

    registry = {}
    for row in con.execute(
        """
        SELECT chain,dex,pool,token0,token1
        FROM universe_pool_registry
        """
    ):
        key = (row["chain"], row["dex"], row["pool"].lower())
        registry[key] = dict(row)

    seismic = defaultdict(list)
    events = []
    seismic_count = 0
    for row in con.execute(
        """
        SELECT id,chain,dex,pool,observed_at,
               previous_state,next_state,score,
               price_z,volume_z,txns_z,liquidity_ratio,evidence_count,reason
        FROM universe_seismic_evaluation_v1
        ORDER BY chain,dex,pool,observed_at,id
        """
    ):
        t = parse_time(row["observed_at"])
        if t is None:
            continue
        key = (row["chain"], row["dex"], row["pool"].lower())
        item = dict(row)
        item["t"] = t
        seismic[key].append(item)
        seismic_count += 1

        if (
            row["next_state"] in {"WARM", "HOT"}
            and row["previous_state"] != row["next_state"]
        ):
            events.append((t, key, item))

    seismic_times = {
        key: [row["t"] for row in rows]
        for key, rows in seismic.items()
    }

    events.sort(key=lambda item: (item[0], item[2]["id"]))
    relevant_keys = sorted({key for _, key, _ in events})

    print(
        f"SEISMIC_LOADED rows={seismic_count} replay_events={len(events)} "
        f"relevant_pools={len(relevant_keys)}",
        flush=True,
    )

    observations = defaultdict(list)
    observation_count = 0

    for pool_number, key in enumerate(relevant_keys, 1):
        if pool_number == 1 or pool_number % 250 == 0:
            print(
                f"OBS_LOAD_PROGRESS {pool_number}/{len(relevant_keys)} "
                f"rows={observation_count}",
                flush=True,
            )

        chain, dex, pool = key
        for row in con.execute(
            """
            SELECT id,chain,dex,pool,source,observed_at,
                   price_usd,liquidity_usd,volume_m5_usd,
                   buys_m5,sells_m5,txns_m5,change_m5
            FROM universe_market_observation_v1
            WHERE chain = ?
              AND dex = ?
              AND pool = ?
              AND price_usd IS NOT NULL
              AND price_usd > 0
            ORDER BY observed_at,id
            """,
            (chain, dex, pool),
        ):
            t = parse_time(row["observed_at"])
            if t is None:
                continue
            item = dict(row)
            item["t"] = t
            item["price_usd"] = float(item["price_usd"])
            observations[key].append(item)
            observation_count += 1

    observation_times = {
        key: [row["t"] for row in rows]
        for key, rows in observations.items()
    }

    print(
        f"OBSERVATIONS_LOADED rows={observation_count} "
        f"pools={len(observations)}",
        flush=True,
    )

    output_rows = []
    skipped_no_observation = 0

    for event_number, (event_t, key, event) in enumerate(events, 1):
        if event_number % 1000 == 0:
            print(
                f"PROGRESS {event_number}/{len(events)} replayable={len(output_rows)}",
                flush=True,
            )

        obs_rows = observations.get(key)
        obs_times = observation_times.get(key)
        if not obs_rows or not obs_times:
            skipped_no_observation += 1
            continue

        decision_t = event_t + args.decision_delay_seconds

        event_obs = latest_at_or_before(obs_rows, event_t, obs_times)
        decision_obs = latest_at_or_before(obs_rows, decision_t, obs_times)

        if event_obs is None or decision_obs is None:
            skipped_no_observation += 1
            continue

        event_price = float(event_obs["price_usd"])
        decision_price = float(decision_obs["price_usd"])

        pre = window(obs_rows, event_obs["t"], decision_t, obs_times)
        if not pre:
            skipped_no_observation += 1
            continue

        pre_prices = [float(row["price_usd"]) for row in pre]
        pre_mfe = pct(max(pre_prices), event_price)
        pre_mae = pct(min(pre_prices), event_price)

        state_rows = seismic.get(key, [])
        state_times = seismic_times.get(key, [])
        state_at_decision = latest_state_at_or_before(
            state_rows,
            decision_t,
            state_times,
        )

        promoted_t = None
        if event["next_state"] == "WARM":
            promoted_t = first_hot_after(
                state_rows,
                event_t,
                decision_t,
                state_times,
            )

        buys = decision_obs["buys_m5"]
        sells = decision_obs["sells_m5"]
        txns = decision_obs["txns_m5"]

        flow_imbalance = None
        if buys is not None and sells is not None:
            denom = int(buys) + int(sells)
            if denom > 0:
                flow_imbalance = (int(buys) - int(sells)) / denom

        future_values = {}
        for name, seconds in HORIZONS.items():
            end_t = decision_t + seconds
            path = window(
                obs_rows,
                decision_obs["t"],
                end_t,
                obs_times,
            )

            if path:
                prices = [float(row["price_usd"]) for row in path]
                future_values[f"eval_mfe_{name}_pct"] = pct(
                    max(prices),
                    decision_price,
                )
                future_values[f"eval_mae_{name}_pct"] = pct(
                    min(prices),
                    decision_price,
                )
            else:
                future_values[f"eval_mfe_{name}_pct"] = None
                future_values[f"eval_mae_{name}_pct"] = None

            horizon_obs = first_at_or_after(
                obs_rows,
                end_t,
                max_gap=max(300, seconds * 0.25),
                times=obs_times,
            )
            future_values[f"eval_return_{name}_pct"] = (
                None
                if horizon_obs is None
                else pct(
                    float(horizon_obs["price_usd"]),
                    decision_price,
                )
            )

        path24 = window(
            obs_rows,
            decision_obs["t"],
            decision_t + HORIZONS["24h"],
            obs_times,
        )

        time_to_peak_24h = None
        first_below_decision = None

        if path24:
            peak = max(path24, key=lambda row: float(row["price_usd"]))
            time_to_peak_24h = max(0.0, peak["t"] - decision_t)

            for row in path24:
                if row["t"] <= decision_t:
                    continue
                if float(row["price_usd"]) < decision_price:
                    first_below_decision = row["t"] - decision_t
                    break

        meta = registry.get(key, {})
        output = {
            "event_id": event["id"],
            "chain": key[0],
            "dex": key[1],
            "pool": key[2],
            "token0": meta.get("token0"),
            "token1": meta.get("token1"),
            "entry_state": event["next_state"],
            "previous_state": event["previous_state"],
            "event_time": iso_utc(event_t),
            "decision_time": iso_utc(decision_t),
            "decision_delay_seconds": args.decision_delay_seconds,
            "state_at_decision": state_at_decision,
            "promoted_warm_to_hot_before_decision": promoted_t is not None,
            "seconds_to_hot": (
                None if promoted_t is None else promoted_t - event_t
            ),
            "event_price": event_price,
            "decision_price": decision_price,
            "event_observation_age_seconds": event_t - event_obs["t"],
            "decision_observation_age_seconds": decision_t - decision_obs["t"],
            "pre_decision_return_pct": pct(decision_price, event_price),
            "pre_decision_mfe_pct": pre_mfe,
            "pre_decision_mae_pct": pre_mae,
            "pre_decision_samples": len(pre),
            "decision_liquidity_usd": decision_obs["liquidity_usd"],
            "decision_volume_m5_usd": decision_obs["volume_m5_usd"],
            "decision_buys_m5": buys,
            "decision_sells_m5": sells,
            "decision_txns_m5": txns,
            "decision_change_m5": decision_obs["change_m5"],
            "decision_flow_imbalance": flow_imbalance,
            "event_score": event["score"],
            "event_price_z": event["price_z"],
            "event_volume_z": event["volume_z"],
            "event_txns_z": event["txns_z"],
            "event_liquidity_ratio": event["liquidity_ratio"],
            "event_evidence_count": event["evidence_count"],
            "event_reason": event["reason"],
            "eval_time_to_peak_24h_seconds": time_to_peak_24h,
            "eval_first_below_decision_seconds": first_below_decision,
        }
        output.update(future_values)
        output_rows.append(output)

    if not output_rows:
        raise SystemExit("no replayable WARM/HOT events found")

    csv_path = out_dir / "events.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    state_counts = Counter(row["entry_state"] for row in output_rows)

    hot_rows = [
        row for row in output_rows
        if row["entry_state"] == "HOT"
    ]
    warm_rows = [
        row for row in output_rows
        if row["entry_state"] == "WARM"
    ]
    warm_promoted_rows = [
        row for row in warm_rows
        if row["promoted_warm_to_hot_before_decision"]
    ]
    warm_not_promoted_rows = [
        row for row in warm_rows
        if not row["promoted_warm_to_hot_before_decision"]
    ]

    summary = {
        "contract": "OPPORTUNITY_REPLAY_DATASET_V1",
        "database": str(db_path),
        "read_only": True,
        "decision_delay_seconds": args.decision_delay_seconds,
        "event_count": len(output_rows),
        "skipped_no_observation": skipped_no_observation,
        "entry_state_counts": dict(state_counts),
        "warm_promoted_to_hot_before_decision": len(warm_promoted_rows),
        "cohorts": {
            "HOT": cohort_summary(hot_rows),
            "WARM": cohort_summary(warm_rows),
            "WARM_PROMOTED_TO_HOT": cohort_summary(warm_promoted_rows),
            "WARM_NOT_PROMOTED": cohort_summary(warm_not_promoted_rows),
        },
        "median_event_observation_age_seconds": median(
            row["event_observation_age_seconds"] for row in output_rows
        ),
        "median_decision_observation_age_seconds": median(
            row["decision_observation_age_seconds"] for row in output_rows
        ),
        "median_pre_decision_return_pct": median(
            row["pre_decision_return_pct"] for row in output_rows
        ),
        "median_hot_pre_decision_return_pct": median(
            row["pre_decision_return_pct"]
            for row in output_rows
            if row["entry_state"] == "HOT"
        ),
        "median_warm_pre_decision_return_pct": median(
            row["pre_decision_return_pct"]
            for row in output_rows
            if row["entry_state"] == "WARM"
        ),
        "median_eval_mfe_1h_pct": median(
            row["eval_mfe_1h_pct"] for row in output_rows
        ),
        "median_eval_mfe_6h_pct": median(
            row["eval_mfe_6h_pct"] for row in output_rows
        ),
        "median_eval_mfe_24h_pct": median(
            row["eval_mfe_24h_pct"] for row in output_rows
        ),
        "median_eval_mae_24h_pct": median(
            row["eval_mae_24h_pct"] for row in output_rows
        ),
        "runtime_seconds": round(time.monotonic() - started, 3),
        "events_csv": str(csv_path),
    }

    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    con.close()


if __name__ == "__main__":
    main()
