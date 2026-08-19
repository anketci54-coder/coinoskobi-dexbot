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
        "sl_price": 0.885,
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


def make_manager(price, position=None):
    manager = PaperManager.__new__(PaperManager)
    manager.db = FakeDB([position or make_position()])
    manager.price = FakePrice(price)
    manager.learning_feed = None
    manager.hybrid_exit_evidence = None
    manager._learning_replay_after_id = 0
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


def test_manager_runs_adaptive_protection_without_optional_hybrid_evidence():
    manager = make_manager(1.30)
    result = manager.process()
    assert manager.db.closed == []
    assert result[0]["data"]["action"] == "HOLD"
    assert result[0]["data"]["reason"] == "NO_EXIT_CONDITION"
    assert result[0]["data"]["hybrid_exit"]["bound"] is True
    _, values = manager.db.updated[0]
    assert values["sl_price"] > 0.885


def test_manager_closes_at_persisted_stop_without_hybrid_evidence():
    manager = make_manager(0.88)
    result = manager.process()
    trade_id, values = manager.db.closed[0]
    assert trade_id == 1
    assert values["exit_price"] == 0.88
    assert values["close_reason"] == "PERSISTED_STOP_LOSS"
    assert values["roi"] <= -0.10
    assert result[0]["data"]["action"] == "CLOSE"
    assert result[0]["data"]["reason"] == "PERSISTED_STOP_LOSS"


def test_manager_persisted_stop_dominates_after_large_drop():
    position = make_position()
    position["highest_price"] = 1.30
    manager = make_manager(0.50, position=position)
    result = manager.process()
    trade_id, values = manager.db.closed[0]
    assert trade_id == 1
    assert values["exit_price"] == 0.50
    assert values["roi"] <= -0.10
    assert values["close_reason"] == "PERSISTED_STOP_LOSS"
    assert result[0]["data"]["reason"] == "PERSISTED_STOP_LOSS"


def test_manager_catastrophic_drop_cannot_remain_open_when_persisted_stop_exists():
    position = make_position()
    position["highest_price"] = 1.40
    manager = make_manager(0.0001, position=position)
    result = manager.process()
    assert len(manager.db.closed) == 1
    trade_id, values = manager.db.closed[0]
    assert trade_id == 1
    assert values["close_reason"] == "PERSISTED_STOP_LOSS"
    assert result[0]["data"]["status"] == "CLOSED"
    assert result[0]["data"]["action"] == "CLOSE"


def test_missing_persisted_stop_uses_controller_without_optional_evidence():
    position = make_position()
    position["sl_price"] = None
    manager = make_manager(0.50, position=position)
    result = manager.process()
    assert manager.db.closed == []
    assert result[0]["data"]["action"] == "HOLD"
    assert result[0]["data"]["reason"] == "NO_EXIT_CONDITION"
    assert result[0]["data"]["hybrid_exit"]["bound"] is True
