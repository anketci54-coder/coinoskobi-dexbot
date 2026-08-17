from app.paper.manager import PaperManager


class FakePrice:
    def __init__(self, price):
        self.price = price

    def get_price(self, token):
        return self.price


class FakeDB:
    def __init__(self, positions):
        self.positions = positions
        self.updated = []
        self.closed = []

    def open_positions(self):
        return self.positions

    def update_position(self, trade_id, values):
        self.updated.append((trade_id, values))

    def close_position(self, trade_id, values=None):
        self.closed.append((trade_id, values))


def make_position():
    return {
        "id": 1,
        "token": "0x0000000000000000000000000000000000000001",
        "entry_price": 1.0,
        "current_price": 1.0,
        "highest_price": 1.0,
        "lowest_price": 1.0,
        "amount_bnb": 0.01,
        "token_amount": 0.01,
        "gas_buy": 0.0,
        "gas_sell": 0.0,
        "swap_fee": 0.0,
        "buy_tax": 0.0,
        "sell_tax": 0.0,
        "slippage": 0.0,
        "mev": 0.0,
        "created_at": "2026-08-09T00:00:00+00:00",
        "closed_at": None,
    }


def make_manager(price):
    manager = PaperManager.__new__(PaperManager)
    manager.db = FakeDB([make_position()])
    manager.price = FakePrice(price)
    return manager


def test_manager_updates_open_position_with_database_contract():
    manager = make_manager(1.05)

    result = manager.process()

    trade_id, values = manager.db.updated[0]

    assert trade_id == 1
    assert values["current_price"] == 1.05
    assert values["highest_price"] == 1.05
    assert values["lowest_price"] == 1.0
    assert values["gross_pnl"] > 0
    assert values["net_pnl"] > 0
    assert values["roi"] > 0
    assert manager.db.closed == []
    assert result[0]["data"]["action"] == "HOLD"


def test_manager_closes_take_profit_with_database_contract():
    manager = make_manager(1.30)

    result = manager.process()

    trade_id, values = manager.db.closed[0]

    assert trade_id == 1
    assert values["current_price"] == 1.30
    assert values["exit_price"] == 1.30
    assert values["highest_price"] == 1.30
    assert values["lowest_price"] == 1.0
    assert values["close_reason"] == "TAKE_PROFIT"
    assert values["gross_pnl"] > 0
    assert values["net_pnl"] > 0
    assert values["roi"] >= 0.20
    assert values["closed_at"]
    assert result[0]["data"]["action"] == "CLOSE"
    assert result[0]["data"]["reason"] == "TAKE_PROFIT"


def test_manager_closes_stop_loss_with_database_contract():
    manager = make_manager(0.80)

    result = manager.process()

    trade_id, values = manager.db.closed[0]

    assert trade_id == 1
    assert values["exit_price"] == 0.80
    assert values["close_reason"] == "STOP_LOSS"
    assert values["roi"] <= -0.10
    assert result[0]["data"]["reason"] == "STOP_LOSS"


def test_manager_hard_stop_loss_dominates_trailing_after_large_drop():
    position = make_position()
    position["highest_price"] = 1.30

    manager = PaperManager.__new__(PaperManager)
    manager.db = FakeDB([position])
    manager.price = FakePrice(0.50)
    manager.learning_feed = None
    manager._learning_replay_after_id = 0

    result = manager.process()

    trade_id, values = manager.db.closed[0]

    assert trade_id == 1
    assert values["exit_price"] == 0.50
    assert values["roi"] <= -0.10
    assert values["close_reason"] == "STOP_LOSS"
    assert result[0]["data"]["reason"] == "STOP_LOSS"
