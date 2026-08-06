from app.paper.database import PaperDatabase
from app.paper.cache_price import CachePrice


class PaperManager:

    TAKE_PROFIT = 0.20
    STOP_LOSS = -0.10

    def __init__(self):

        self.db = PaperDatabase()
        self.price = CachePrice()

    def process(self):

        positions = self.db.open_positions()

        print(f"Açık Pozisyon : {len(positions)}")

        for pos in positions:

            token = pos["token"]

            try:
                current = self.price.get_price(token)
                print(f"[PRICE] token={token} current={current}")
            except Exception as e:
                print(f"[ERROR] token={token} error={e}")
                continue

            highest = max(pos["highest_price"], current)
            lowest = min(pos["lowest_price"], current)

            entry = pos["entry_price"]

            print(f"[ENTRY] token={token} entry={entry}")

            if entry <= 0:
                print(f"[SKIP] token={token} entry_price<=0")
                continue

            token_amount = pos["token_amount"]

            if token_amount <= 0:
                continue

            current_value = token_amount * current

            gross = current_value - pos["amount_bnb"]

            trade_value = pos["amount_bnb"]

            swap_fee_cost = trade_value * ((pos["swap_fee"] or 0) / 100)
            buy_tax_cost = trade_value * ((pos["buy_tax"] or 0) / 100)
            sell_tax_cost = trade_value * ((pos["sell_tax"] or 0) / 100)
            slippage_cost = trade_value * ((pos["slippage"] or 0) / 100)
            mev_cost = trade_value * ((pos["mev"] or 0) / 100)

            fees = (
                (pos["gas_buy"] or 0)
                + (pos["gas_sell"] or 0)
                + swap_fee_cost
                + buy_tax_cost
                + sell_tax_cost
                + slippage_cost
                + mev_cost
            )

            net = gross - fees

            roi = (
                net / pos["amount_bnb"]
                if pos["amount_bnb"] > 0
                else 0
            )

            self.db.update_position(

                pos["id"],

                current_price=current,
                highest_price=highest,
                lowest_price=lowest

            )

            print(
                f"{token[:10]}... "
                f"ROI={roi*100:.2f}% "
                f"Current={current:.10f}"
            )

            trailing_price = highest * 0.90

            if current <= trailing_price and highest > entry:

                self.db.close_position(

                    pos["id"],
                    current,
                    gross,
                    net,
                    roi,
                    "TRAILING_STOP"

                )

                print(">>> TRAILING STOP")

            elif roi >= self.TAKE_PROFIT:

                self.db.close_position(

                    pos["id"],
                    current,
                    gross,
                    net,
                    roi,
                    "TAKE_PROFIT"

                )

                print(">>> TAKE PROFIT")

            elif roi <= self.STOP_LOSS:

                self.db.close_position(

                    pos["id"],
                    current,
                    gross,
                    net,
                    roi,
                    "STOP_LOSS"

                )

                print(">>> STOP LOSS")

        open_count = self.db.conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'"
        ).fetchone()[0]

        closed_count = self.db.conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED'"
        ).fetchone()[0]

        tp_count = self.db.conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE close_reason='TAKE_PROFIT'"
        ).fetchone()[0]

        sl_count = self.db.conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE close_reason='STOP_LOSS'"
        ).fetchone()[0]

        total_net = self.db.conn.execute(
            "SELECT COALESCE(SUM(net_pnl),0) FROM paper_trades"
        ).fetchone()[0]

        avg_roi = self.db.conn.execute(
            "SELECT COALESCE(AVG(roi),0) FROM paper_trades WHERE status='CLOSED'"
        ).fetchone()[0]

        print()
        total_trades = self.db.conn.execute(
            "SELECT COUNT(*) FROM paper_trades"
        ).fetchone()[0]

        best = self.db.conn.execute(
            "SELECT COALESCE(MAX(roi),0) FROM paper_trades WHERE status='CLOSED'"
        ).fetchone()[0]

        worst = self.db.conn.execute(
            "SELECT COALESCE(MIN(roi),0) FROM paper_trades WHERE status='CLOSED'"
        ).fetchone()[0]

        print("=" * 60)
        print("PAPER SUMMARY")
        print("=" * 60)
        print(f"Total Trades   : {total_trades}")
        print(f"Open Positions : {open_count}")
        print(f"Closed Trades  : {closed_count}")
        print(f"Take Profit    : {tp_count}")
        print(f"Stop Loss      : {sl_count}")
        print(f"Total Net PnL  : {total_net:.8f} BNB")
        print(f"Average ROI    : {avg_roi*100:.2f}%")
        print(f"Best ROI       : {best*100:.2f}%")
        print(f"Worst ROI      : {worst*100:.2f}%")
        print("=" * 60)
        print("Paper Manager tamamlandı.")


if __name__ == "__main__":

    PaperManager().process()

