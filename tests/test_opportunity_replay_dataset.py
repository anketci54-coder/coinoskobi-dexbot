import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "lab"
    / "opportunity_replay_v1"
    / "build_dataset.py"
)

spec = importlib.util.spec_from_file_location(
    "opportunity_replay_build_dataset",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_latest_at_or_before_never_reads_future_row():
    rows = [
        {"t": 100.0, "price_usd": 10.0},
        {"t": 110.0, "price_usd": 11.0},
        {"t": 121.0, "price_usd": 999.0},
    ]

    selected = module.latest_at_or_before(rows, 120.0)

    assert selected["t"] == 110.0
    assert selected["price_usd"] == 11.0


def test_pre_decision_window_excludes_future_price():
    rows = [
        {"t": 100.0, "price_usd": 10.0},
        {"t": 110.0, "price_usd": 11.0},
        {"t": 120.0, "price_usd": 10.5},
        {"t": 121.0, "price_usd": 1000.0},
    ]

    selected = module.window(rows, 100.0, 120.0)

    assert [row["t"] for row in selected] == [100.0, 110.0, 120.0]
    assert max(row["price_usd"] for row in selected) == 11.0


def test_warm_to_hot_promotion_is_bounded_by_decision_time():
    states = [
        {"t": 100.0, "next_state": "WARM"},
        {"t": 111.0, "next_state": "HOT"},
        {"t": 130.0, "next_state": "HOT"},
    ]

    assert module.first_hot_after(states, 100.0, 120.0) == 111.0
    assert module.first_hot_after(states, 100.0, 110.0) is None


def test_latest_state_at_decision_is_causal():
    states = [
        {"t": 100.0, "next_state": "WARM"},
        {"t": 115.0, "next_state": "HOT"},
        {"t": 130.0, "next_state": "COLD"},
    ]

    assert module.latest_state_at_or_before(states, 120.0) == "HOT"
