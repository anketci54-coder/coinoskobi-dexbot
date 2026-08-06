from app.paper.database import PaperDatabase


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

        print()
        print("=" * 60)
        print("PORTFOLIO SUMMARY")
        print("=" * 60)
        print(f"Total Trades   : {total}")
        print(f"Open Positions : {open_count}")
        print(f"Closed Trades  : {closed_count}")
        print(f"Take Profit    : {tp}")
        print(f"Stop Loss      : {sl}")
        print(f"Trailing Stop  : {trailing}")
        print(f"Total Net PnL  : {net:.8f} BNB")
        print(f"Average ROI    : {avg_roi*100:.2f}%")
        print(f"Best ROI       : {best*100:.2f}%")
        print(f"Worst ROI      : {worst*100:.2f}%")
        print("=" * 60)


if __name__ == "__main__":
    Portfolio().summary()
