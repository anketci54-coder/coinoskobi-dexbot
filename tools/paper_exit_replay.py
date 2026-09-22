#!/usr/bin/env python3
import json
import sqlite3
from collections import defaultdict

DB = "data/paper_trades.db"

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

trades = con.execute("""
SELECT id, token, entry_price, status, net_pnl_usdt,
       sl_price, tp_price, entry_amount_usdt, created_at
FROM paper_trades
WHERE entry_price > 0
  AND entry_amount_usdt > 0
ORDER BY id
""").fetchall()

obs = defaultdict(list)
for r in con.execute("""
SELECT position_id, observed_at, price
FROM paper_price_observations
WHERE price > 0
ORDER BY position_id, observed_at, id
"""):
    obs[r["position_id"]].append((r["observed_at"], float(r["price"])))

def replay(prices, entry, mode):
    peak = entry

    for ts, price in prices:
        ret = price / entry - 1.0
        peak = max(peak, price)

        if mode == "tp5_sl5":
            if ret >= .05: return price, ts, "TP"
            if ret <= -.05: return price, ts, "SL"

        elif mode == "tp10_sl5":
            if ret >= .10: return price, ts, "TP"
            if ret <= -.05: return price, ts, "SL"

        elif mode == "tp15_sl7":
            if ret >= .15: return price, ts, "TP"
            if ret <= -.07: return price, ts, "SL"

        elif mode == "lock5":
            if ret <= -.07: return price, ts, "SL"
            if peak >= entry * 1.05 and price <= entry * 1.01:
                return price, ts, "PROFIT_LOCK"

        elif mode == "trail5":
            if ret <= -.07: return price, ts, "SL"
            if peak >= entry * 1.05 and price <= peak * .95:
                return price, ts, "TRAIL"

        elif mode == "trail8":
            if ret <= -.08: return price, ts, "SL"
            if peak >= entry * 1.08 and price <= peak * .92:
                return price, ts, "TRAIL"

    if prices:
        return prices[-1][1], prices[-1][0], "LAST"
    return entry, None, "NO_DATA"

modes = [
    "tp5_sl5",
    "tp10_sl5",
    "tp15_sl7",
    "lock5",
    "trail5",
    "trail8",
]

stats = {
    m: {
        "n": 0, "wins": 0, "losses": 0,
        "sum": 0.0, "best": -999.0, "worst": 999.0
    } for m in modes
}

rows = []

for t in trades:
    p = obs.get(t["id"], [])
    if not p:
        continue

    entry = float(t["entry_price"])
    path_prices = [x[1] for x in p]

    mfe = (max(path_prices) / entry - 1) * 100
    mae = (min(path_prices) / entry - 1) * 100

    row = {
        "id": t["id"],
        "status": t["status"],
        "mfe": mfe,
        "mae": mae,
    }

    for mode in modes:
        exit_price, ts, reason = replay(p, entry, mode)
        ret = (exit_price / entry - 1) * 100

        s = stats[mode]
        s["n"] += 1
        s["sum"] += ret
        s["best"] = max(s["best"], ret)
        s["worst"] = min(s["worst"], ret)

        if ret > 0:
            s["wins"] += 1
        elif ret < 0:
            s["losses"] += 1

        row[mode] = ret

    rows.append(row)

print("\n=== OFFLINE PAPER EXIT REPLAY ===")
print("DB READ-ONLY")
print("RUNTIME/PANEL UNTOUCHED")
print("TRADES_WITH_PRICE_PATH =", len(rows))

print("\n=== STRATEGY RESULTS ===")
for mode in modes:
    s = stats[mode]
    if not s["n"]:
        continue
    avg = s["sum"] / s["n"]
    wr = s["wins"] / s["n"] * 100

    print(
        f"{mode:12s} "
        f"N={s['n']:3d} "
        f"WIN={wr:6.2f}% "
        f"AVG={avg:+7.2f}% "
        f"BEST={s['best']:+7.2f}% "
        f"WORST={s['worst']:+7.2f}%"
    )

print("\n=== BIGGEST MISSED PROFITS ===")
for r in sorted(rows, key=lambda x: x["mfe"], reverse=True)[:20]:
    best_mode = max(modes, key=lambda m: r[m])
    print(
        f"ID={r['id']:4d} "
        f"MFE={r['mfe']:+7.2f}% "
        f"MAE={r['mae']:+7.2f}% "
        f"BEST={best_mode}:{r[best_mode]:+7.2f}%"
    )

print("\n=== DONE ===")
con.close()
