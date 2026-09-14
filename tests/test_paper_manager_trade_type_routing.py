import app.paper.manager as manager_module
from app.paper.manager import PaperManager


class FakeDB:
    def __init__(self, position):
        self.position = position

    def open_positions(self):
        return [dict(self.position)]


class FakePrice:
    def get_price(self, token):
        return 1.0


def _position(*, trade_type, trade_policy):
    return {
        "id": 1,
        "token": "0xtest",
        "entry_price": 1.0,
        "current_price": 1.0,
        "highest_price": 1.0,
        "lowest_price": 1.0,
        "token_amount": 1.0,
        "trade_type": trade_type,
        "trade_policy": trade_policy,
        "mathematical_plan_json": "{}",
    }


def _manager(position):
    manager = object.__new__(PaperManager)
    manager.db = FakeDB(position)
    manager.price = FakePrice()
    manager.learning_feed = None
    manager.hybrid_exit_evidence = None
    manager._learning_replay_after_id = 0
    manager.replay_closed_outcomes = lambda: []
    return manager


def test_manager_routes_by_trade_type_before_legacy_policy(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "decode_plan",
        lambda raw: {"contract": "mathematical_trade_plan"},
    )

    manager = _manager(
        _position(
            trade_type="NORMAL",
            trade_policy="VUR_KAC",
        )
    )

    manager._process_normal_math_position = (
        lambda *args: {"route": "NORMAL"}
    )
    manager._process_vur_kac_position = (
        lambda *args: {"route": "VUR_KAC"}
    )

    assert manager.process() == [{"route": "NORMAL"}]


def test_manager_routes_vur_kac_by_trade_type_even_if_legacy_policy_normal(
    monkeypatch,
):
    monkeypatch.setattr(
        manager_module,
        "decode_plan",
        lambda raw: {"contract": "mathematical_trade_plan"},
    )

    manager = _manager(
        _position(
            trade_type="VUR_KAC",
            trade_policy="NORMAL",
        )
    )

    manager._process_normal_math_position = (
        lambda *args: {"route": "NORMAL"}
    )
    manager._process_vur_kac_position = (
        lambda *args: {"route": "VUR_KAC"}
    )

    assert manager.process() == [{"route": "VUR_KAC"}]


def test_manager_keeps_legacy_policy_only_as_missing_trade_type_fallback(
    monkeypatch,
):
    monkeypatch.setattr(
        manager_module,
        "decode_plan",
        lambda raw: {"contract": "mathematical_trade_plan"},
    )

    manager = _manager(
        _position(
            trade_type=None,
            trade_policy="VUR_KAC",
        )
    )

    manager._process_normal_math_position = (
        lambda *args: {"route": "NORMAL"}
    )
    manager._process_vur_kac_position = (
        lambda *args: {"route": "VUR_KAC"}
    )

    assert manager.process() == [{"route": "VUR_KAC"}]
