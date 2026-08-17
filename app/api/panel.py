from pathlib import Path
import sqlite3

from fastapi import FastAPI


BASE_DIR = Path(__file__).resolve().parents[2]
PAPER_DB = BASE_DIR / "data" / "paper_trades.db"

app = FastAPI(
    title="Coinoskobi Panel API",
    version="1.0",
)


def query(sql, params=()):
    # Read-only SQLite connection: panel cannot write.
    uri = f"file:{PAPER_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in conn.execute(sql, params).fetchall()
        ]
    finally:
        conn.close()


@app.get("/healthz")
def health():
    rows = query("SELECT 1 AS ok")
    return {
        "status": "ok",
        "database": rows[0]["ok"] == 1,
        "mode": "READ_ONLY",
    }


@app.get("/api/status")
def status():
    rows = query(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN id > 250
                      AND pool IS NOT NULL
                      AND trim(pool) <> ''
                     THEN 1 ELSE 0 END) AS new_generation,
            SUM(CASE WHEN id > 250
                      AND pool IS NOT NULL
                      AND trim(pool) <> ''
                      AND status='OPEN'
                     THEN 1 ELSE 0 END) AS open_positions,
            SUM(CASE WHEN id > 250
                      AND pool IS NOT NULL
                      AND trim(pool) <> ''
                      AND status='CLOSED'
                     THEN 1 ELSE 0 END) AS closed_positions
        FROM paper_trades
        """
    )
    return rows[0]


@app.get("/api/positions")
def positions():
    return query(
        """
        SELECT
            id,
            symbol,
            token,
            pool,
            status,
            entry_price,
            current_price,
            highest_price,
            tp_price,
            sl_price,
            gross_pnl,
            net_pnl,
            roi,
            close_reason,
            created_at,
            closed_at
        FROM paper_trades
        WHERE id > 250
          AND pool IS NOT NULL
          AND trim(pool) <> ''
        ORDER BY id DESC
        LIMIT 100
        """
    )


@app.get("/api/performance")
def performance():
    rows = query(
        """
        SELECT
            COUNT(*) AS closed,
            SUM(CASE WHEN net_pnl > 0
                     THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN net_pnl <= 0
                     THEN 1 ELSE 0 END) AS losses,
            ROUND(
                100.0 *
                SUM(CASE WHEN net_pnl > 0
                         THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0),
                2
            ) AS win_rate_pct,
            ROUND(AVG(roi) * 100, 2) AS avg_roi_pct,
            ROUND(SUM(net_pnl), 8) AS net_total
        FROM paper_trades
        WHERE id > 250
          AND pool IS NOT NULL
          AND trim(pool) <> ''
          AND status='CLOSED'
        """
    )
    return rows[0]


@app.get("/api/exits")
def exits():
    return query(
        """
        SELECT
            close_reason,
            COUNT(*) AS trades,
            ROUND(AVG(roi) * 100, 2) AS avg_roi_pct,
            ROUND(SUM(net_pnl), 8) AS net_total
        FROM paper_trades
        WHERE id > 250
          AND pool IS NOT NULL
          AND trim(pool) <> ''
          AND status='CLOSED'
        GROUP BY close_reason
        ORDER BY trades DESC
        """
    )


@app.get("/api/positions-v2")
def positions_v2():
    import json

    rows = query(
        """
        SELECT
            id,
            symbol,
            token,
            pool,
            status,
            entry_price,
            current_price,
            highest_price,
            tp_price,
            sl_price,
            gross_pnl,
            net_pnl,
            roi,
            close_reason,
            created_at,
            closed_at,
            opening_context_json
        FROM paper_trades
        WHERE id > 250
          AND pool IS NOT NULL
          AND trim(pool) <> ''
        ORDER BY id DESC
        LIMIT 100
        """
    )

    result = []

    for row in rows:
        item = dict(row)
        raw = item.pop("opening_context_json", None)

        try:
            context = json.loads(raw) if raw else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            context = {}

        signals = dict(context.get("raw_signals") or {})
        attribution = dict(context.get("signal_attribution") or {})
        baseline = dict(context.get("exit_baseline") or {})

        item["entry_evidence"] = {
            "captured_at_entry": bool(
                context.get("captured_at_entry")
            ),
            "hindsight_reconstructed": bool(
                context.get("hindsight_reconstructed")
            ),
            "strategy_decision": signals.get(
                "strategy_decision"
            ),
            "unified_decision": signals.get(
                "unified_decision"
            ),
            "score": signals.get("unified_score"),
            "confidence": signals.get(
                "unified_confidence"
            ),
            "hard_block": bool(
                signals.get("hard_block")
            ),
            "sellability": signals.get(
                "sellability_status"
            ),
            "coverage": signals.get(
                "unified_coverage"
            ),
            "signal_attribution": attribution,
            "entry_price": baseline.get(
                "entry_price"
            ),
            "stop_loss_price": baseline.get(
                "stop_loss_price"
            ),
            "take_profit_price": baseline.get(
                "take_profit_price"
            ),
        }

        item["authority"] = {
            "decision": False,
            "execution": False,
            "live": False,
            "wallet": False,
            "read_only": True,
        }

        result.append(item)

    return result
