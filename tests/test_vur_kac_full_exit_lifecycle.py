import json

import app.paper.manager as manager_module
from app.paper.manager import PaperManager


class FakePaperDatabase:
    def __init__(self):
        self.updates = []
        self.closed = []

    def record_price_observation(
        self,
        position_id,
        price,
    ):
        return None

    def price_observations(
        self,
        position_id,
    ):
        return [
            1.0,
            1.2,
            1.3,
        ]

    def update_position(
        self,
        position_id,
        values,
    ):
        self.updates.append(
            (
                position_id,
                dict(values),
            )
        )
        return True

    def close_position(
        self,
        position_id,
        values,
    ):
        self.closed.append(
            (
                position_id,
                dict(values),
            )
        )
        return True

    def apply_partial_realization(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "VUR_KAC must never partial-realize"
        )


def _manager():
    manager = PaperManager.__new__(
        PaperManager
    )
    manager.db = FakePaperDatabase()
    manager.learning_feed = None
    manager.hybrid_exit_evidence = None
    return manager


def _position():
    return {
        "id": 1,
        "token": "0xtoken",
        "trade_type": "VUR_KAC",
        "entry_price": 1.0,
        "entry_amount_usdt": 100.0,
        "token_amount": 100.0,
        "remaining_cost_basis_usdt": 100.0,
        "realized_pnl_usdt": 0.0,
        "realized_proceeds_usdt": 0.0,
        "realized_gross_proceeds_usdt": 0.0,
        "sl_price": 0.50,
        "math_state_json": json.dumps({}),
        "tp1_done": 1,
        "tp2_done": 1,
        "runner_active": 1,
    }


def _plan():
    return {
        "statistics": {
            "prices": [],
        },
        "sl": {
            "risk_log_distance": 0.20,
        },
        "cost_model": {
            "sell_retention_known": 1.0,
            "sell_gas_usd": 0.0,
        },
    }


def test_vur_kac_realize_is_single_full_exit(
    monkeypatch,
):
    manager = _manager()

    monkeypatch.setattr(
        manager_module,
        "dynamic_stop_price",
        lambda **kwargs: 0.50,
    )

    monkeypatch.setattr(
        manager_module,
        "mathematical_vur_kac_state",
        lambda **kwargs: {
            "ready": True,
            "reason": "VUR_KAC_REALIZE",
            "realize": True,
            "continuation_edge_usdt": -1.0,
            "remaining_net_profit_usdt": 30.0,
        },
    )

    result = (
        manager
        ._process_vur_kac_position(
            _position(),
            1.30,
            1.30,
            1.0,
            _plan(),
        )
    )

    assert (
        result["data"]["action"]
        == "CLOSE"
    )

    assert (
        result["data"]["reason"]
        == "MATHEMATICAL_VUR_KAC_EXIT"
    )

    assert len(
        manager.db.closed
    ) == 1

    close_data = (
        manager.db.closed[0][1]
    )

    assert (
        close_data["token_amount"]
        == 0.0
    )


def test_vur_kac_hold_never_partial_realizes(
    monkeypatch,
):
    manager = _manager()

    monkeypatch.setattr(
        manager_module,
        "dynamic_stop_price",
        lambda **kwargs: 0.50,
    )

    monkeypatch.setattr(
        manager_module,
        "mathematical_vur_kac_state",
        lambda **kwargs: {
            "ready": True,
            "reason": "CONTINUATION_POSITIVE",
            "realize": False,
            "continuation_edge_usdt": 5.0,
            "remaining_net_profit_usdt": 30.0,
        },
    )

    result = (
        manager
        ._process_vur_kac_position(
            _position(),
            1.30,
            1.30,
            1.0,
            _plan(),
        )
    )

    assert (
        result["data"]["action"]
        == "HOLD"
    )

    assert (
        result["data"]["trade_type"]
        == "VUR_KAC"
    )

    assert (
        result["data"]["full_exit_only"]
        is True
    )

    assert manager.db.closed == []
