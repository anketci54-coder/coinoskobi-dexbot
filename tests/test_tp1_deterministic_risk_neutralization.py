import json

import pytest

import app.paper.manager as manager_module
from app.paper.manager import PaperManager


class FakePaperDatabase:
    def __init__(self):
        self.partial_calls = []
        self.updates = []

    def record_price_observation(self, position_id, price):
        return None

    def price_observations(self, position_id):
        return [1.0, 1.5, 2.0]

    def update_position(self, position_id, values):
        self.updates.append((position_id, dict(values)))
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
            "realization": dict(realization),
            "math_state_json": math_state_json,
        })
        return True


def _manager():
    manager = PaperManager.__new__(PaperManager)
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


def _position(*, tp1_done=0):
    if tp1_done:
        tokens = 80.0
        basis = 80.0
        realized_pnl = 20.0
        realized_proceeds = 40.0
    else:
        tokens = 100.0
        basis = 100.0
        realized_pnl = 0.0
        realized_proceeds = 0.0

    return {
        "id": 1,
        "token": "0xtoken",
        "entry_price": 1.0,
        "entry_amount_usdt": 100.0,
        "token_amount": tokens,
        "remaining_cost_basis_usdt": basis,
        "realized_pnl_usdt": realized_pnl,
        "realized_proceeds_usdt": realized_proceeds,
        "realized_gross_proceeds_usdt": realized_proceeds,
        "sl_price": 0.50,
        "risk_amount_usdt": 20.0,
        "math_state_json": json.dumps({
            "initial_net_risk_usdt": 20.0,
        }),
        "tp1_done": int(tp1_done),
        "tp2_done": 0,
        "runner_active": 0,
    }


def _flow_not_ready(**kwargs):
    return {
        "ready": False,
        "reason": "FLOW_EVIDENCE_NOT_READY",
        "realize": False,
        "continuation_positive": False,
        "continuation_edge_usdt": None,
        "remaining_net_profit_usdt": 100.0,
    }


def _patch_unknown_flow(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "dynamic_stop_price",
        lambda **kwargs: 0.50,
    )
    monkeypatch.setattr(
        manager_module,
        "mathematical_vur_kac_state",
        _flow_not_ready,
    )


def test_tp1_neutralizes_initial_risk_without_flow_confirmation(
    monkeypatch,
):
    manager = _manager()
    _patch_unknown_flow(monkeypatch)

    result = manager._process_vur_kac_position(
        _position(tp1_done=0),
        2.0,
        2.0,
        1.0,
        _plan(),
    )

    assert result["data"]["action"] == "PARTIAL_TP1"
    assert result["data"]["status"] == "OPEN"
    assert result["data"]["reason"] == "MATHEMATICAL_REALIZATION"

    assert len(manager.db.partial_calls) == 1
    call = manager.db.partial_calls[0]
    assert call["stage"] == "TP1"
    assert call["price"] == pytest.approx(2.0)
    assert call["realization"]["realized_pnl_usdt"] == pytest.approx(20.0)
    assert call["realization"]["fraction"] == pytest.approx(0.20)


def test_tp1_waits_when_initial_risk_cannot_be_neutralized(
    monkeypatch,
):
    manager = _manager()
    _patch_unknown_flow(monkeypatch)

    result = manager._process_vur_kac_position(
        _position(tp1_done=0),
        1.10,
        1.10,
        1.0,
        _plan(),
    )

    assert result["data"]["action"] == "HOLD"
    assert manager.db.partial_calls == []


def test_tp2_still_waits_for_persistent_vur_kac_when_flow_is_unknown(
    monkeypatch,
):
    manager = _manager()
    _patch_unknown_flow(monkeypatch)

    result = manager._process_vur_kac_position(
        _position(tp1_done=1),
        2.0,
        2.0,
        1.0,
        _plan(),
    )

    assert result["data"]["action"] == "HOLD"
    assert manager.db.partial_calls == []
