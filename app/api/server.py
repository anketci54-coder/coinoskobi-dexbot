from fastapi import FastAPI
from app.paper.database import PaperDatabase

app = FastAPI(
    title="Coinoskobi API",
    version="1.0"
)

db = PaperDatabase()


@app.get("/")
def root():
    return {
        "service": "Coinoskobi",
        "status": "running"
    }


@app.get("/portfolio")
def portfolio():

    conn = db.conn

    total = conn.execute(
        "SELECT COUNT(*) FROM paper_trades"
    ).fetchone()[0]

    open_positions = conn.execute(
        "SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'"
    ).fetchone()[0]

    closed = conn.execute(
        "SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED'"
    ).fetchone()[0]

    tp = conn.execute(
        "SELECT COUNT(*) FROM paper_trades WHERE close_reason='TAKE_PROFIT'"
    ).fetchone()[0]

    sl = conn.execute(
        "SELECT COUNT(*) FROM paper_trades WHERE close_reason='STOP_LOSS'"
    ).fetchone()[0]

    trailing = conn.execute(
        "SELECT COUNT(*) FROM paper_trades WHERE close_reason='TRAILING_STOP'"
    ).fetchone()[0]

    net = conn.execute(
        "SELECT COALESCE(SUM(net_pnl),0) FROM paper_trades"
    ).fetchone()[0]

    avg = conn.execute(
        "SELECT COALESCE(AVG(roi),0) FROM paper_trades WHERE status='CLOSED'"
    ).fetchone()[0]

    return {
        "total_trades": total,
        "open_positions": open_positions,
        "closed_trades": closed,
        "take_profit": tp,
        "stop_loss": sl,
        "trailing_stop": trailing,
        "net_pnl": net,
        "average_roi": avg
    }


@app.get("/positions")
def positions():

    rows = db.conn.execute(
        """
        SELECT
            id,
            token,
            symbol,
            entry_price,
            current_price,
            roi,
            highest_price,
            lowest_price,
            tp_price,
            sl_price
        FROM paper_trades
        WHERE status='OPEN'
        ORDER BY id
        """
    ).fetchall()

    return [dict(r) for r in rows]


@app.get("/history")
def history():

    rows = db.conn.execute(
        """
        SELECT *
        FROM paper_trades
        ORDER BY id DESC
        LIMIT 100
        """
    ).fetchall()

    return [dict(r) for r in rows]
