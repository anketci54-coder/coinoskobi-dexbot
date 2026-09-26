import app.paper.manager as manager_module
from app.config.contracts import USDT
from app.paper.manager import PaperManager


TOKEN = "0x" + "11" * 20
POOL = "0x" + "22" * 20


def _position():
    return {
        "id": 77,
        "trade_type": "NORMAL",
        "token": TOKEN,
        "pool": POOL,
        "token_amount": 1.25,
        "sell_tax": 0.0,
    }


def test_phase15h_sell_uses_usdt_quote_and_position_token_amount(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        manager_module,
        "analyze_exit_feasibility",
        lambda token, pool: {
            "success": True,
            "data": {
                "quote_token": USDT,
                "token_decimals": 18,
                "runtime_price_latest_block": 123456,
            },
        },
    )

    def fake_simulate(**kwargs):
        captured.update(kwargs)
        return {
            "status": "SUCCESS",
            "block": {
                "number": kwargs["block_number"],
                "chain_id": 56,
            },
            "received_quote_raw": 123,
            "gas_used": 456,
        }

    monkeypatch.setattr(
        manager_module,
        "simulate_paper_sell",
        fake_simulate,
    )

    manager = PaperManager.__new__(PaperManager)
    result = manager._runtime_phase15h_sell_evidence(
        pos=_position(),
        current_price=2.0,
        stage="NORMAL_STOP_LOSS",
        exit_fraction=0.4,
    )

    assert result["sell"]["status"] == "SUCCESS"
    assert captured["quote_token"].lower() == USDT.lower()
    assert captured["pool"].lower() == POOL.lower()
    assert captured["seed_token_raw"] == 500000000000000000


def test_phase15h_sell_rejects_non_usdt_quote_without_simulation(monkeypatch):
    monkeypatch.setattr(
        manager_module,
        "analyze_exit_feasibility",
        lambda token, pool: {
            "success": True,
            "data": {
                "quote_token": "0x" + "33" * 20,
                "token_decimals": 18,
                "runtime_price_latest_block": 123456,
            },
        },
    )

    def should_not_run(**kwargs):
        raise AssertionError("simulation must not run for non-USDT quote")

    monkeypatch.setattr(
        manager_module,
        "simulate_paper_sell",
        should_not_run,
    )

    manager = PaperManager.__new__(PaperManager)
    result = manager._runtime_phase15h_sell_evidence(
        pos=_position(),
        current_price=2.0,
        stage="NORMAL_STOP_LOSS",
        exit_fraction=1.0,
    )

    assert result["sell"]["status"] == "UNKNOWN"
    assert result["sell"]["evidence_reason"] == "NON_USDT_ROUTE_REJECTED"
