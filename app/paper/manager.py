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
            except Exception as e:
                print(token, e)
                continue

            highest = max(pos["highest_price"], current)
            lowest = min(pos["lowest_price"], current)

            entry = pos["entry_price"]

            if entry <= 0:
                continue

            roi = (current - entry) / entry

            gross = (current - entry) * pos["amount_bnb"]
            net = gross

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

            if roi >= self.TAKE_PROFIT:

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

        print()
        print("Paper Manager tamamlandı.")


if __name__ == "__main__":

    PaperManager().process()

