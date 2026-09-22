#!/usr/bin/env python3
import sqlite3
from datetime import datetime

DB = "data/paper_trades.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

trades = con.execute("""
SELECT id, token, pool, created_at, entry_price, status,
       close_reason, net_pnl_usdt, entry_amount_usdt
FROM paper_trades
WHERE entry_price > 0
  AND entry_amount_usdt > 0
ORDER BY id
""").fetchall()

def ret(price, entry):
    return (price / entry - 1.0) * 100.0

def first_at_or_after(path, start, minutes):
    target = (dt(start).timestamp() + minutes * 60)
    candidates = [
        (abs(dt(r["observed_at"]).timestamp() - target), r)
        for r in path
        if dt(r["observed_at"]).timestamp() >= target
    ]
    if not candidates:
        return None
    r = min(candidates, key=lambda x: x[0])[1]
    return r["price"]

rows = []

for t in trades:
    path = con.execute("""
        SELECT observed_at, price
        FROM paper_price_observations
        WHERE position_id=? AND price>0
        ORDER BY observed_at,id
    """, (t["id"],)).fetchall()

    if not path:
        continue

    entry = float(t["entry_price"])
    prices = [float(x["price"]) for x in path]

    r = {
        "id": t["id"],
        "status": t["status"],
        "reason": t["close_reason"],
        "mfe": ret(max(prices), entry),
        "mae": ret(min(prices), entry),
    }

    for m in (5,15,30,60):
        p = first_at_or_after(path, t["created_at"], m)
        r[f"r{m}"] = None if p is None else ret(float(p), entry)

    rows.append(r)

print("=== OFFLINE ENTRY PATH ANALYSIS ===")
print("DB READ-ONLY / RUNTIME UNTOUCHED")
print("N =", len(rows))

print("\n=== PATH DISTRIBUTION ===")
for m in (5,15,30,60):
    vals=[r[f"r{m}"] for r in rows if r[f"r{m}"] is not None]
    pos=sum(v>0 for v in vals)
    avg=sum(vals)/len(vals) if vals else 0
    print(f"{m:2d}m N={len(vals):3d} POS={pos/len(vals)*100 if vals else 0:6.2f}% AVG={avg:+8.2f}%")

print("\n=== CLEAN WINNERS: MAE > -5%, MFE >= +10% ===")
clean=[r for r in rows if r["mae"] > -5 and r["mfe"] >= 10]
for r in sorted(clean,key=lambda x:x["mfe"],reverse=True):
    print(
        f"ID={r['id']:4d} "
        f"5m={r['r5'] if r['r5'] is not None else 999:+7.2f}% "
        f"15m={r['r15'] if r['r15'] is not None else 999:+7.2f}% "
        f"30m={r['r30'] if r['r30'] is not None else 999:+7.2f}% "
        f"60m={r['r60'] if r['r60'] is not None else 999:+7.2f}% "
        f"MAE={r['mae']:+7.2f}% MFE={r['mfe']:+7.2f}%"
    )

print("\n=== BAD ENTRIES: MAE <= -10% ===")
bad=[r for r in rows if r["mae"] <= -10]
for r in sorted(bad,key=lambda x:x["mae"])[:50]:
    print(
        f"ID={r['id']:4d} "
        f"5m={r['r5'] if r['r5'] is not None else 999:+7.2f}% "
        f"15m={r['r15'] if r['r15'] is not None else 999:+7.2f}% "
        f"30m={r['r30'] if r['r30'] is not None else 999:+7.2f}% "
        f"60m={r['r60'] if r['r60'] is not None else 999:+7.2f}% "
        f"MAE={r['mae']:+7.2f}% MFE={r['mfe']:+7.2f}%"
    )

print("\n=== COUNTS ===")
print("CLEAN_WINNERS =", len(clean))
print("BAD_ENTRIES   =", len(bad))
print("OTHER         =", len(rows)-len(clean)-len(bad))

con.close()
