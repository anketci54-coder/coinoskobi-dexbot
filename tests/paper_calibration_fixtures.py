"""Synthetic current-model proof for calibration math fixtures only."""
import json

from app.config.contracts import USDT

TOKEN = "0x" + "12" * 20
POOL = "0x" + "34" * 20
HASH = "0x" + "ab" * 32


def execution(side, position_id=1, *, stage="NORMAL_STOP_LOSS", fraction=1.0):
    received = "received_token_raw" if side == "BUY" else "received_quote_raw"
    proof = {
        "contract": "phase15h_transaction_simulation_v1", "side": side,
        "status": "SUCCESS", "fill_status": "SIMULATED_RECIPIENT_DELTA",
        "token": TOKEN, "pool": POOL, "quote_token": USDT,
        "block": {"number": 123, "hash": HASH, "chain_id": 56},
        received: 100, "recipient_balance_delta_raw": 100,
    }
    if side == "SELL":
        proof.update(paper_position_id=position_id, exit_stage=stage,
                     paper_exit_fraction=fraction)
    return {side.lower(): proof}


def opening(price=1.0):
    stamp = "2026-09-27T10:00:00+00:00"
    return {
        "admission_provenance": {
            "contract": "corrected_paper_v1", "verified_at": stamp,
            "price_integrity": {"state": "VERIFIED_EXTREME", "price": price},
        },
        "price_observation": {
            "token": TOKEN, "pool": POOL, "quote_token": USDT,
            "chain": "bsc", "dex": "pancakeswap_v2", "source": "dexscreener",
            "price_usd": price, "observed_at": stamp,
        },
        "phase15h_execution": execution("BUY"),
    }


def stamp_current_model(db, table="paper_trades"):
    columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    for column in ("token", "pool", "opening_context_json", "closing_execution_json"):
        if column not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
    for row in db.execute(f"SELECT rowid, id, entry_price FROM {table}").fetchall():
        rowid, position_id, price = row
        db.execute(f"UPDATE {table} SET token=?, pool=?, opening_context_json=?, closing_execution_json=? WHERE rowid=?",
                   (TOKEN, POOL, json.dumps(opening(price)), json.dumps(execution("SELL", position_id)), rowid))
