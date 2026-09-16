from app.learning.runtime_outcome_feed import (
    RuntimeLearningOutcomeFeed,
)
from app.paper.manager import PaperManager


class FakeDB:
    def __init__(self):
        self.closed = []

    def open_positions(self):
        return [{
            "id": 123,
            "token": "0xtoken",
            "created_at": (
                "2026-01-01T00:00:00+00:00"
            ),
            "closed_at": "",
            "highest_price": 1.0,
            "lowest_price": 1.0,
            "entry_price": 1.0,
            "token_amount": 1.0,
            "amount_bnb": 1.0,
            "swap_fee": 0,
            "buy_tax": 0,
            "sell_tax": 0,
            "slippage": 0,
            "mev": 0,
            "gas_buy": 0,
            "gas_sell": 0,
            "sl_price": 2.0,
        }]

    def update_position(
        self,
        position_id,
        data,
    ):
        return True

    def close_position(
        self,
        position_id,
        data,
    ):
        self.closed.append(
            (
                position_id,
                dict(data),
            )
        )

        return True


class FakePrice:
    def get_price(
        self,
        token,
    ):
        return 2.0


def test_real_paper_close_feeds_phase11():
    feed = RuntimeLearningOutcomeFeed()

    manager = PaperManager(
        learning_feed=feed
    )

    manager.db = FakeDB()
    manager.price = FakePrice()

    results = manager.process()

    assert len(results) == 1

    row = results[0][
        "data"
    ]

    assert row[
        "action"
    ] == "CLOSE"

    assert row[
        "reason"
    ] == "PERSISTED_STOP_LOSS"

    assert row[
        "learning"
    ][
        "state"
    ] == "OBSERVED"

    assert feed.event_count == 1

    learning_row = (
        row["learning"][
            "payload"
        ]
    )

    assert (
        learning_row[
            "classification"
        ][
            "outcome_class"
        ]
        == "VALID_SIGNAL"
    )

    close_data = (
        manager.db.closed[0][1]
    )

    lifecycle = learning_row[
        "lifecycle_snapshot"
    ]

    assert (
        lifecycle["highest_price"]
        == close_data["highest_price"]
    )

    assert (
        lifecycle["lowest_price"]
        == close_data["lowest_price"]
    )

    assert lifecycle["gross_pnl_usdt"] is None
    assert lifecycle["net_pnl_usdt"] is None
    assert (
        lifecycle["gross_pnl"]
        == close_data["gross_pnl"]
    )
    assert (
        lifecycle["net_pnl"]
        == close_data["net_pnl"]
    )
    assert lifecycle["pnl_currency"] == "BNB"

    assert (
        feed.calibration_snapshot()
        ["state"]
        == "READY"
    )


def test_hold_does_not_create_outcome():
    feed = RuntimeLearningOutcomeFeed()

    manager = PaperManager(
        learning_feed=feed
    )

    manager.db = FakeDB()
    manager.db.open_positions = lambda: [
        {
            **FakeDB().open_positions()[0],
            "sl_price": None,
        }
    ]

    class HoldPrice:
        def get_price(
            self,
            token,
        ):
            return 1.0

    manager.price = HoldPrice()

    results = manager.process()

    assert results[
        0
    ][
        "data"
    ][
        "action"
    ] == "HOLD"

    assert results[
        0
    ][
        "data"
    ][
        "learning"
    ] is None

    assert feed.event_count == 0



def test_replay_legacy_close_falls_back_to_persisted_generic_pnl():
    feed = RuntimeLearningOutcomeFeed()

    manager = PaperManager(
        learning_feed=feed
    )

    class ReplayDB:
        def closed_positions(
            self,
            *,
            after_id=0,
        ):
            return [{
                "id": 321,
                "token": "0xlegacy",
                "created_at": (
                    "2026-01-01T00:00:00+00:00"
                ),
                "closed_at": (
                    "2026-01-01T01:00:00+00:00"
                ),
                "entry_price": 1.0,
                "exit_price": 0.98,
                "highest_price": 1.05,
                "lowest_price": 0.97,
                "roi": -0.02,
                "gross_pnl": 1.0,
                "net_pnl": -2.0,
                "gross_pnl_usdt": None,
                "net_pnl_usdt": None,
                "close_reason": (
                    "PERSISTED_STOP_LOSS"
                ),
            }]

    manager.db = ReplayDB()

    results = manager.replay_closed_outcomes()

    assert len(results) == 1
    assert feed.event_count == 1

    row = results[0]["payload"]

    lifecycle = row[
        "lifecycle_snapshot"
    ]

    assert lifecycle[
        "gross_pnl_usdt"
    ] is None

    assert lifecycle[
        "net_pnl_usdt"
    ] is None

    assert lifecycle[
        "gross_pnl"
    ] == 1.0

    assert lifecycle[
        "net_pnl"
    ] == -2.0

    assert lifecycle[
        "pnl_currency"
    ] == "BNB"
