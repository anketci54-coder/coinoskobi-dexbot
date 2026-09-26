import json

import app.paper.manager as manager_module
from app.config.contracts import USDT
from app.paper.manager import PaperManager


class FakeDB:
    def __init__(self):
        self.partial_calls = []
        self.closed = []
        self.updates = []

    def record_price_observation(self, position_id, price):
        return None

    def price_observations(self, position_id):
        return [1.0, 1.3, 1.6]

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

    def close_position(self, position_id, values):
        self.closed.append((position_id, dict(values)))
        return True


def _manager():
    manager = PaperManager.__new__(PaperManager)
    manager.db = FakeDB()
    manager.learning_feed = None
    manager.hybrid_exit_evidence = None
    return manager


def _plan():
    return {
        "statistics": {
            "prices": [1.0, 1.2, 1.4],
        },
        "sl": {
            "risk_log_distance": 0.20,
        },
        "cost_model": {
            "sell_retention_known": 1.0,
            "sell_gas_usd": 0.0,
        },
    }


def _normal_position(
    *,
    tp1_done=0,
    tp2_done=0,
    runner_active=0,
):
    return {
        "id": 7,
        "token": "0x0000000000000000000000000000000000000002",
        "pool": "0x0000000000000000000000000000000000000003",
        "trade_type": "NORMAL",
        "entry_price": 1.0,
        "entry_amount_usdt": 100.0,
        "token_amount": 100.0 if not tp1_done else 80.0,
        "remaining_cost_basis_usdt": 100.0 if not tp1_done else 80.0,
        "realized_pnl_usdt": 0.0 if not tp1_done else 20.0,
        "realized_proceeds_usdt": 0.0 if not tp1_done else 40.0,
        "realized_gross_proceeds_usdt": 0.0 if not tp1_done else 40.0,
        "sl_price": 0.50,
        "tp_price": 1.20,
        "risk_amount_usdt": 20.0,
        "sell_tax": 1.0,
        "math_state_json": json.dumps({
            "initial_net_risk_usdt": 20.0,
        }),
        "tp1_done": tp1_done,
        "tp2_done": tp2_done,
        "runner_active": runner_active,
    }


def _vur_kac_position():
    return {
        "id": 9,
        "token": "0x0000000000000000000000000000000000000004",
        "pool": "0x0000000000000000000000000000000000000005",
        "trade_type": "VUR_KAC",
        "entry_price": 1.0,
        "entry_amount_usdt": 100.0,
        "token_amount": 100.0,
        "remaining_cost_basis_usdt": 100.0,
        "realized_pnl_usdt": 0.0,
        "realized_proceeds_usdt": 0.0,
        "realized_gross_proceeds_usdt": 0.0,
        "sl_price": 0.50,
        "sell_tax": 0.0,
        "math_state_json": json.dumps({}),
        "tp1_done": 1,
        "tp2_done": 1,
        "runner_active": 1,
    }


def test_phase15h_sell_evidence_preserves_trade_type_stage_and_notional(
    monkeypatch,
    caplog,
):
    manager = _manager()
    calls = []

    monkeypatch.setattr(
        manager_module,
        "analyze_exit_feasibility",
        lambda token, pool: {
            "success": True,
            "data": {
                "runtime_price_latest_block": 123456,
                "quote_token": USDT,
                "token_decimals": 18,
            },
        },
    )

    def fake_sell(**kwargs):
        calls.append(dict(kwargs))
        return {
            "contract": "phase15h_transaction_simulation_v1",
            "side": "SELL",
            "status": "SUCCESS",
            "block": {
                "number": kwargs["block_number"],
                "hash": "0xabc",
                "chain_id": 56,
            },
            "received_quote_raw": 456,
            "recipient_balance_delta_raw": 456,
            "gas_used": 111000,
            "fill_status": "SIMULATED_RECIPIENT_DELTA",
        }

    monkeypatch.setattr(
        manager_module,
        "simulate_paper_sell",
        fake_sell,
    )
    caplog.set_level(
        "INFO",
        logger="app.paper.manager",
    )

    evidence = manager._runtime_phase15h_sell_evidence(
        pos=_normal_position(),
        current_price=2.0,
        stage="NORMAL_TP1",
        exit_fraction=0.25,
        exit_notional_usdt=60.0,
    )

    sell = evidence["sell"]
    assert sell["status"] == "SUCCESS"
    assert sell["trade_type"] == "NORMAL"
    assert sell["exit_stage"] == "NORMAL_TP1"
    assert sell["paper_exit_fraction"] == 0.25
    assert sell["paper_exit_notional_usdt"] == 60.0
    assert calls[0]["block_number"] == 123456
    assert calls[0]["quote_token"].lower() == USDT.lower()
    assert calls[0]["pool"].lower() == _normal_position()["pool"].lower()
    assert calls[0]["seed_token_raw"] == 25 * 10 ** 18
    assert calls[0]["fee_on_transfer"] is True
    assert "PHASE15H_RUNTIME_SELL" in caplog.text
    assert "trade_type=NORMAL" in caplog.text
    assert "stage=NORMAL_TP1" in caplog.text


def test_normal_tp1_and_tp2_bind_sell_once_after_realization():
    for position, expected_action, expected_stage in (
        (
            _normal_position(),
            "PARTIAL_TP1",
            "NORMAL_TP1",
        ),
        (
            _normal_position(
                tp1_done=1,
                tp2_done=0,
            ),
            "PARTIAL_TP2",
            "NORMAL_TP2",
        ),
    ):
        manager = _manager()
        calls = []

        def fake_phase15h(**kwargs):
            calls.append(dict(kwargs))
            return {
                "sell": {
                    "status": "SUCCESS",
                    "trade_type": "NORMAL",
                    "exit_stage": kwargs["stage"],
                }
            }

        manager._runtime_phase15h_sell_evidence = fake_phase15h

        result = manager._process_normal_math_position(
            position,
            2.0,
            2.0,
            1.0,
            _plan(),
        )

        assert result["data"]["action"] == expected_action
        assert len(calls) == 1
        assert calls[0]["stage"] == expected_stage
        assert 0 < float(calls[0]["exit_fraction"]) < 1
        assert (
            result["data"]["phase15h_execution"]["sell"]["status"]
            == "SUCCESS"
        )


def test_normal_tp3_trend_exit_binds_full_sell(monkeypatch):
    manager = _manager()
    calls = []

    manager._runtime_phase15h_sell_evidence = (
        lambda **kwargs: (
            calls.append(dict(kwargs))
            or {
                "sell": {
                    "status": "SUCCESS",
                    "trade_type": "NORMAL",
                    "exit_stage": kwargs["stage"],
                }
            }
        )
    )

    monkeypatch.setattr(
        manager_module,
        "dynamic_stop_price",
        lambda **kwargs: 1.50,
    )

    result = manager._process_normal_math_position(
        _normal_position(
            tp1_done=1,
            tp2_done=1,
            runner_active=1,
        ),
        1.40,
        2.0,
        1.0,
        _plan(),
    )

    assert result["data"]["action"] == "CLOSE"
    assert result["data"]["reason"] == "NORMAL_TP3_TREND_EXIT"
    assert len(calls) == 1
    assert calls[0]["stage"] == "NORMAL_TP3_TREND_EXIT"
    assert calls[0]["exit_fraction"] == 1.0
    assert result["data"]["trade_type"] == "NORMAL"


def test_vur_kac_is_full_exit_only_and_binds_full_sell(monkeypatch):
    manager = _manager()
    calls = []

    manager._runtime_phase15h_sell_evidence = (
        lambda **kwargs: (
            calls.append(dict(kwargs))
            or {
                "sell": {
                    "status": "SUCCESS",
                    "trade_type": "VUR_KAC",
                    "exit_stage": kwargs["stage"],
                }
            }
        )
    )

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

    result = manager._process_vur_kac_position(
        _vur_kac_position(),
        1.30,
        1.30,
        1.0,
        _plan(),
    )

    assert result["data"]["action"] == "CLOSE"
    assert result["data"]["reason"] == "MATHEMATICAL_VUR_KAC_EXIT"
    assert len(manager.db.partial_calls) == 0
    assert len(calls) == 1
    assert calls[0]["stage"] == "MATHEMATICAL_VUR_KAC_EXIT"
    assert calls[0]["exit_fraction"] == 1.0
    assert result["data"]["trade_type"] == "VUR_KAC"


def test_full_close_stays_open_when_phase15h_sell_is_not_proven():
    manager = _manager()
    manager._runtime_phase15h_sell_evidence = lambda **_kwargs: {
        "sell": {
            "status": "REVERT",
            "trade_type": "NORMAL",
            "exit_stage": "NORMAL_STOP_LOSS",
        }
    }

    result = manager._close_math(
        _normal_position(),
        0.40,
        1.20,
        0.40,
        _plan(),
        "NORMAL_STOP_LOSS",
    )

    assert result["data"]["action"] == "SKIP"
    assert result["data"]["status"] == "OPEN"
    assert result["data"]["reason"] == "PHASE15H_SELL_NOT_PROVEN"
    assert result["data"]["phase15h_execution"]["sell"]["status"] == "REVERT"
    assert manager.db.closed == []


def test_tp1_realization_is_not_applied_when_phase15h_sell_is_not_proven():
    manager = _manager()
    manager._runtime_phase15h_sell_evidence = lambda **_kwargs: {
        "sell": {
            "status": "UNKNOWN",
            "trade_type": "NORMAL",
            "exit_stage": "NORMAL_TP1",
        }
    }

    result = manager._process_normal_math_position(
        _normal_position(),
        2.0,
        2.0,
        1.0,
        _plan(),
    )

    assert result["data"]["action"] == "SKIP"
    assert result["data"]["status"] == "OPEN"
    assert result["data"]["reason"] == "PHASE15H_SELL_NOT_PROVEN"
    assert result["data"]["phase15h_execution"]["sell"]["status"] == "UNKNOWN"
    assert manager.db.partial_calls == []


def test_tp2_realization_is_not_applied_when_phase15h_sell_is_not_proven():
    manager = _manager()
    manager._runtime_phase15h_sell_evidence = lambda **_kwargs: {
        "sell": {
            "status": "REVERT",
            "trade_type": "NORMAL",
            "exit_stage": "NORMAL_TP2",
        }
    }

    result = manager._process_normal_math_position(
        _normal_position(tp1_done=1, tp2_done=0),
        2.0,
        2.0,
        1.0,
        _plan(),
    )

    assert result["data"]["action"] == "SKIP"
    assert result["data"]["status"] == "OPEN"
    assert result["data"]["reason"] == "PHASE15H_SELL_NOT_PROVEN"
    assert result["data"]["phase15h_execution"]["sell"]["status"] == "REVERT"
    assert manager.db.partial_calls == []
