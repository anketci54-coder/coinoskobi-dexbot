import json

import app.paper.manager as manager_module
from app.paper.manager import PaperManager


class FakeDB:
    def __init__(self):
        self.partial_calls = []
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
            1.3,
            1.6,
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


def manager():
    m = PaperManager.__new__(
        PaperManager
    )
    m.db = FakeDB()
    m.learning_feed = None
    m.hybrid_exit_evidence = None
    m._runtime_phase15h_sell_evidence = (
        lambda **kwargs: {
            "sell": {
                "status": "SUCCESS",
                "trade_type": "NORMAL",
                "exit_stage": kwargs.get("stage"),
            }
        }
    )
    return m


def plan():
    return {
        "statistics": {
            "prices": [
                1.0,
                1.2,
                1.4,
            ],
        },
        "sl": {
            "risk_log_distance": 0.20,
        },
        "cost_model": {
            "sell_retention_known": 1.0,
            "sell_gas_usd": 0.0,
        },
    }


def position(
    *,
    tp1_done=1,
    tp2_done=0,
    runner_active=0,
):
    return {
        "id": 1,
        "token": "0xtoken",
        "trade_type": "NORMAL",
        "entry_price": 1.0,
        "entry_amount_usdt": 100.0,
        "token_amount": 80.0,
        "remaining_cost_basis_usdt": 80.0,
        "realized_pnl_usdt": 20.0,
        "realized_proceeds_usdt": 40.0,
        "realized_gross_proceeds_usdt": 40.0,
        "sl_price": 0.50,
        "tp_price": 1.20,
        "risk_amount_usdt": 20.0,
        "math_state_json": json.dumps({
            "initial_net_risk_usdt": 20.0,
        }),
        "tp1_done": tp1_done,
        "tp2_done": tp2_done,
        "runner_active": runner_active,
    }


def test_normal_tp2_recovers_principal():
    m = manager()

    result = (
        m._process_normal_math_position(
            position(),
            2.0,
            2.0,
            1.0,
            plan(),
        )
    )

    assert (
        result["data"]["action"]
        == "PARTIAL_TP2"
    )

    assert (
        result["data"]["reason"]
        == "NORMAL_PRINCIPAL_RECOVERY"
    )

    assert len(
        m.db.partial_calls
    ) == 1

    assert (
        m.db.partial_calls[0][
            "stage"
        ]
        == "TP2"
    )

    assert (
        result["data"][
            "runner_active"
        ]
        is True
    )


def test_normal_tp3_runner_uses_dynamic_floor(
    monkeypatch,
):
    m = manager()

    monkeypatch.setattr(
        manager_module,
        "dynamic_stop_price",
        lambda **kwargs: 1.50,
    )

    result = (
        m._process_normal_math_position(
            position(
                tp2_done=1,
                runner_active=1,
            ),
            1.40,
            2.0,
            1.0,
            plan(),
        )
    )

    assert (
        result["data"]["action"]
        == "CLOSE"
    )

    assert (
        result["data"]["reason"]
        == "NORMAL_TP3_TREND_EXIT"
    )

    assert len(
        m.db.closed
    ) == 1


def test_tp1_activation_price_is_not_full_exit():
    m = manager()

    pos = position(
        tp1_done=1,
        tp2_done=0,
        runner_active=0,
    )

    result = (
        m._process_normal_math_position(
            pos,
            1.25,
            1.25,
            1.0,
            plan(),
        )
    )

    assert not (
        result["data"]["action"]
        == "CLOSE"
        and result["data"]["reason"]
        == "NORMAL_TAKE_PROFIT"
    )



def _pre_tp1_position():
    pos = position(
        tp1_done=0,
        tp2_done=0,
        runner_active=0,
    )
    pos.update({
        "entry_amount_usdt": 100.0,
        "token_amount": 100.0,
        "remaining_cost_basis_usdt": 100.0,
        "realized_pnl_usdt": 0.0,
        "realized_proceeds_usdt": 0.0,
        "realized_gross_proceeds_usdt": 0.0,
        "sl_price": 0.50,
        "math_state_json": json.dumps({
            "initial_net_risk_usdt": 20.0,
        }),
    })
    return pos


def test_normal_pre_tp1_historical_high_does_not_arm_after_restart():
    m = manager()
    pos = _pre_tp1_position()

    result = m._process_normal_math_position(
        pos,
        0.95,
        1.50,
        0.90,
        plan(),
    )

    assert result["data"]["action"] == "HOLD"
    assert m.db.closed == []

    protection_updates = [
        values
        for _, values in m.db.updates
        if "normal_pre_tp1_break_even_armed" in (
            values.get("math_state_json") or ""
        )
    ]
    assert protection_updates == []


def test_normal_pre_tp1_live_cross_arms_break_even_floor():
    m = manager()
    pos = _pre_tp1_position()

    result = m._process_normal_math_position(
        pos,
        1.05,
        1.50,
        0.90,
        plan(),
    )

    assert result["data"]["action"] == "HOLD"
    assert m.db.closed == []

    protection_updates = [
        values
        for _, values in m.db.updates
        if (
            values.get("sl_price") == 1.0
            and "math_state_json" in values
        )
    ]
    assert protection_updates

    state = json.loads(
        protection_updates[0]["math_state_json"]
    )
    assert state[
        "normal_pre_tp1_break_even_armed"
    ] is True
    assert state[
        "normal_pre_tp1_break_even_price"
    ] == 1.0
    assert state[
        "normal_pre_tp1_break_even_armed_price"
    ] == 1.05


def test_normal_pre_tp1_persisted_floor_survives_restart_and_closes_later():
    m = manager()
    pos = _pre_tp1_position()
    pos.update({
        "sl_price": 1.0,
        "math_state_json": json.dumps({
            "initial_net_risk_usdt": 20.0,
            "normal_pre_tp1_break_even_price": 1.0,
            "normal_pre_tp1_break_even_armed": True,
            "normal_pre_tp1_break_even_armed_price": 1.05,
        }),
    })

    result = m._process_normal_math_position(
        pos,
        0.99,
        1.50,
        0.90,
        plan(),
    )

    assert result["data"]["action"] == "CLOSE"
    assert result["data"]["reason"] == (
        "NORMAL_PROFIT_PROTECTION_EXIT"
    )
    assert len(m.db.closed) == 1
    assert m.db.closed[0][1]["close_reason"] == (
        "NORMAL_PROFIT_PROTECTION_EXIT"
    )



def test_normal_pre_tp1_floor_reason_survives_tp1_flag_until_stop_moves():
    m = manager()
    pos = _pre_tp1_position()
    pos.update({
        "tp1_done": 1,
        "sl_price": 1.0,
        "math_state_json": json.dumps({
            "initial_net_risk_usdt": 20.0,
            "normal_pre_tp1_break_even_price": 1.0,
            "normal_pre_tp1_break_even_armed": True,
            "normal_pre_tp1_break_even_armed_price": 1.05,
        }),
    })

    result = m._process_normal_math_position(
        pos,
        0.99,
        1.50,
        0.90,
        plan(),
    )

    assert result["data"]["reason"] == (
        "NORMAL_PROFIT_PROTECTION_EXIT"
    )


def test_normal_runner_stop_is_not_mislabeled_as_break_even_floor():
    m = manager()
    pos = _pre_tp1_position()
    pos.update({
        "tp1_done": 1,
        "tp2_done": 1,
        "runner_active": 1,
        "sl_price": 1.20,
        "math_state_json": json.dumps({
            "initial_net_risk_usdt": 20.0,
            "normal_pre_tp1_break_even_price": 1.0,
            "normal_pre_tp1_break_even_armed": True,
            "normal_pre_tp1_break_even_armed_price": 1.05,
        }),
    })

    result = m._process_normal_math_position(
        pos,
        1.19,
        1.50,
        0.90,
        plan(),
    )

    assert result["data"]["reason"] == (
        "NORMAL_STOP_LOSS"
    )


def test_normal_profit_protection_reason_has_expected_exit_price():
    pos = {
        "sl_price": 1.0,
    }

    assert PaperManager._expected_exit_price(
        pos,
        "NORMAL_PROFIT_PROTECTION_EXIT",
    ) == 1.0



def test_normal_live_arm_preserves_initial_risk_baseline():
    m = manager()
    pos = _pre_tp1_position()
    pos.update({
        "sl_price": 0.90,
        "risk_amount_usdt": None,
        "math_state_json": json.dumps({}),
    })

    realistic_plan = plan()
    realistic_plan["cost_model"] = {
        "sell_retention_known": 0.99,
        "sell_gas_usd": 1.0,
    }

    result = m._process_normal_math_position(
        pos,
        1.10,
        1.10,
        1.0,
        realistic_plan,
    )

    risk_updates = [
        values["risk_amount_usdt"]
        for _, values in m.db.updates
        if "risk_amount_usdt" in values
    ]

    assert risk_updates
    assert abs(risk_updates[0] - 11.9) < 1e-9
    assert result["data"]["action"] == "HOLD"

    protection_updates = [
        values
        for _, values in m.db.updates
        if values.get("sl_price") is not None
    ]
    assert protection_updates
    assert protection_updates[-1]["sl_price"] > 1.0
