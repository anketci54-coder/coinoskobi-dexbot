import app.paper.manager as manager_module
from tests.test_normal_tp2_tp3_runner import manager, plan, position


def test_runner_uses_post_entry_history_when_sufficient(monkeypatch):
    m = manager()
    seen = {}

    def fake_dynamic_stop_price(**kwargs):
        seen["prices"] = list(kwargs["prices"])
        return 1.50

    monkeypatch.setattr(
        manager_module,
        "dynamic_stop_price",
        fake_dynamic_stop_price,
    )

    m._process_normal_math_position(
        position(tp2_done=1, runner_active=1),
        1.40,
        2.0,
        1.0,
        plan(),
    )

    assert seen["prices"] == [1.0, 1.3, 1.6]


def test_runner_falls_back_to_plan_history_when_post_entry_sparse(
    monkeypatch,
):
    m = manager()
    m.db.price_observations = lambda position_id: [1.4]
    seen = {}

    def fake_dynamic_stop_price(**kwargs):
        seen["prices"] = list(kwargs["prices"])
        return 1.50

    monkeypatch.setattr(
        manager_module,
        "dynamic_stop_price",
        fake_dynamic_stop_price,
    )

    m._process_normal_math_position(
        position(tp2_done=1, runner_active=1),
        1.40,
        2.0,
        1.0,
        plan(),
    )

    assert seen["prices"] == [1.0, 1.2, 1.4, 1.4]
