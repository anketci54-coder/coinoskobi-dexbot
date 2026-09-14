import json

import pytest

from app.paper.manager import PaperManager


class FakePaperDatabase:
    def __init__(self):
        self.partial_calls = []
        self.updates = []

    def record_price_observation(
        self,
        position_id,
        price,
    ):
        return None

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

    def apply_partial_realization(
        self,
        position_id,
        *,
        stage,
        price,
        realization,
        math_state_json,
    ):
        self.partial_calls.append({
            "position_id": position_id,
            "stage": stage,
            "price": price,
            "realization": dict(
                realization
            ),
            "math_state_json": (
                math_state_json
            ),
        })
        return True


def _manager():
    manager = PaperManager.__new__(
        PaperManager
    )
    manager.db = FakePaperDatabase()
    manager.learning_feed = None
    manager.hybrid_exit_evidence = None
    return manager


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


def _position():
    return {
        "id": 1,
        "token": "0xtoken",
        "trade_type": "NORMAL",
        "entry_price": 1.0,
        "entry_amount_usdt": 100.0,
        "token_amount": 100.0,
        "remaining_cost_basis_usdt": 100.0,
        "realized_pnl_usdt": 0.0,
        "realized_proceeds_usdt": 0.0,
        "realized_gross_proceeds_usdt": 0.0,
        "sl_price": 0.50,
        "tp_price": 10.0,
        "risk_amount_usdt": 20.0,
        "math_state_json": json.dumps({
            "initial_net_risk_usdt": 20.0,
        }),
        "tp1_done": 0,
        "tp2_done": 0,
        "runner_active": 0,
    }


def test_normal_tp1_neutralizes_initial_risk():
    manager = _manager()

    result = (
        manager
        ._process_normal_math_position(
            _position(),
            2.0,
            2.0,
            1.0,
            _plan(),
        )
    )

    assert (
        result["data"]["action"]
        == "PARTIAL_TP1"
    )
    assert (
        result["data"]["status"]
        == "OPEN"
    )
    assert (
        result["data"]["reason"]
        == "NORMAL_RISK_NEUTRALIZATION"
    )

    assert len(
        manager.db.partial_calls
    ) == 1

    call = (
        manager.db.partial_calls[0]
    )

    assert call["stage"] == "TP1"
    assert call["price"] == pytest.approx(
        2.0
    )

    assert (
        call["realization"][
            "realized_pnl_usdt"
        ]
        == pytest.approx(20.0)
    )

    assert (
        call["realization"][
            "fraction"
        ]
        == pytest.approx(0.20)
    )


def test_normal_tp1_waits_when_risk_not_neutralized():
    manager = _manager()

    result = (
        manager
        ._process_normal_math_position(
            _position(),
            1.10,
            1.10,
            1.0,
            _plan(),
        )
    )

    assert (
        result["data"]["action"]
        == "HOLD"
    )

    assert (
        manager.db.partial_calls
        == []
    )
