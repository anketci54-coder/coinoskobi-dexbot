import logging

from app.paper.database import PaperDatabase

logger = logging.getLogger(__name__)


class Portfolio:

    def __init__(self):
        self.db = PaperDatabase()

    def summary(self):

        conn = self.db.conn

        total = conn.execute(
            "SELECT COUNT(*) FROM paper_trades"
        ).fetchone()[0]

        open_count = conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'"
        ).fetchone()[0]

        closed_count = conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED'"
        ).fetchone()[0]

        tp = conn.execute(
            """
            SELECT COUNT(*)
            FROM paper_trades
            WHERE close_reason='TAKE_PROFIT'
            """
        ).fetchone()[0]

        sl = conn.execute(
            """
            SELECT COUNT(*)
            FROM paper_trades
            WHERE close_reason='STOP_LOSS'
            """
        ).fetchone()[0]

        trailing = conn.execute(
            """
            SELECT COUNT(*)
            FROM paper_trades
            WHERE close_reason='TRAILING_STOP'
            """
        ).fetchone()[0]

        net = conn.execute(
            """
            SELECT COALESCE(SUM(net_pnl),0)
            FROM paper_trades
            """
        ).fetchone()[0]

        avg_roi = conn.execute(
            """
            SELECT COALESCE(AVG(roi),0)
            FROM paper_trades
            WHERE status='CLOSED'
            """
        ).fetchone()[0]

        best = conn.execute(
            """
            SELECT COALESCE(MAX(roi),0)
            FROM paper_trades
            WHERE status='CLOSED'
            """
        ).fetchone()[0]

        worst = conn.execute(
            """
            SELECT COALESCE(MIN(roi),0)
            FROM paper_trades
            WHERE status='CLOSED'
            """
        ).fetchone()[0]

        return {
            "total": total,
            "open": open_count,
            "closed": closed_count,
            "take_profit": tp,
            "stop_loss": sl,
            "trailing_stop": trailing,
            "net_pnl": net,
            "avg_roi": avg_roi,
            "best_roi": best,
            "worst_roi": worst,
        }


if __name__ == "__main__":

    data = Portfolio().summary()

    print()
    print("=" * 60)
    print("PORTFOLIO SUMMARY")
    print("=" * 60)
    print(f"Total Trades   : {data['total']}")
    print(f"Open Positions : {data['open']}")
    print(f"Closed Trades  : {data['closed']}")
    print(f"Take Profit    : {data['take_profit']}")
    print(f"Stop Loss      : {data['stop_loss']}")
    print(f"Trailing Stop  : {data['trailing_stop']}")
    print(f"Total Net PnL  : {data['net_pnl']:.8f} BNB")
    print(f"Average ROI    : {data['avg_roi']*100:.2f}%")
    print(f"Best ROI       : {data['best_roi']*100:.2f}%")
    print(f"Worst ROI      : {data['worst_roi']*100:.2f}%")
    print("=" * 60)
