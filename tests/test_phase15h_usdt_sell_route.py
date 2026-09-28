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


def test_phase15h_sell_standard_success_does_not_probe_fot(monkeypatch):
    calls = []
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
        calls.append(dict(kwargs))
        return {
            "status": "SUCCESS",
            "block": {"number": kwargs["block_number"], "chain_id": 56},
            "received_quote_raw": 123,
            "gas_used": 456,
        }

    monkeypatch.setattr(manager_module, "simulate_paper_sell", fake_simulate)
    manager = PaperManager.__new__(PaperManager)
    result = manager._runtime_phase15h_sell_evidence(
        pos=_position(),
        current_price=2.0,
        stage="NORMAL_STOP_LOSS",
        exit_fraction=1.0,
    )

    assert result["sell"]["status"] == "SUCCESS"
    assert result["sell"]["sell_route_mode"] == "STANDARD"
    assert [c["fee_on_transfer"] for c in calls] == [False]


def test_phase15h_sell_revert_retries_fot_on_same_block_and_amount(monkeypatch):
    calls = []
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
        calls.append(dict(kwargs))
        if not kwargs["fee_on_transfer"]:
            return {
                "status": "REVERT",
                "block": {"number": kwargs["block_number"], "chain_id": 56},
                "received_quote_raw": None,
                "raw": {"errors": [{"message": "execution reverted"}]},
            }
        return {
            "status": "SUCCESS",
            "block": {"number": kwargs["block_number"], "chain_id": 56},
            "received_quote_raw": 777,
            "gas_used": 654,
        }

    monkeypatch.setattr(manager_module, "simulate_paper_sell", fake_simulate)
    manager = PaperManager.__new__(PaperManager)
    result = manager._runtime_phase15h_sell_evidence(
        pos=_position(),
        current_price=2.0,
        stage="NORMAL_TP1",
        exit_fraction=0.4,
    )

    sell = result["sell"]
    assert sell["status"] == "SUCCESS"
    assert sell["received_quote_raw"] == 777
    assert sell["sell_route_mode"] == "FOT_FALLBACK_AFTER_STANDARD_REVERT"
    assert sell["standard_route_revert"]["status"] == "REVERT"
    assert [c["fee_on_transfer"] for c in calls] == [False, True]
    assert calls[0]["block_number"] == calls[1]["block_number"] == 123456
    assert calls[0]["seed_token_raw"] == calls[1]["seed_token_raw"]


def test_phase15h_sell_does_not_hide_revert_when_fot_not_proven(monkeypatch):
    calls = []
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
        calls.append(dict(kwargs))
        return {
            "status": "REVERT",
            "block": {"number": kwargs["block_number"], "chain_id": 56},
            "received_quote_raw": None,
            "raw": {"errors": [{"message": "execution reverted"}]},
        }

    monkeypatch.setattr(manager_module, "simulate_paper_sell", fake_simulate)
    manager = PaperManager.__new__(PaperManager)
    result = manager._runtime_phase15h_sell_evidence(
        pos=_position(),
        current_price=2.0,
        stage="NORMAL_TP1",
        exit_fraction=0.4,
    )

    sell = result["sell"]
    assert sell["status"] == "REVERT"
    assert sell["sell_route_mode"] == "STANDARD_REVERT_FOT_NOT_PROVEN"
    assert sell["fot_fallback_attempt"]["status"] == "REVERT"
    assert [c["fee_on_transfer"] for c in calls] == [False, True]
