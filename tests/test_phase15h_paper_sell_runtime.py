import app.paper.manager as manager_module
from app.paper.manager import (
    PaperManager,
    _runtime_phase15h_sell_evidence,
)


class _Eth:
    block_number = 123456


class _Web3:
    eth = _Eth()


def test_phase15h_runtime_sell_runs_only_after_real_exit(monkeypatch, caplog):
    calls = []

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
        "canonical_bsc_web3",
        _Web3(),
    )
    monkeypatch.setattr(
        manager_module,
        "simulate_paper_sell",
        fake_sell,
    )
    caplog.set_level(
        "INFO",
        logger="app.paper.manager",
    )

    evidence = _runtime_phase15h_sell_evidence(
        position={
            "id": 7,
            "token": "0x0000000000000000000000000000000000000002",
            "sell_tax": 1.0,
        },
        action="PARTIAL_TP1",
    )

    assert evidence["sell"]["status"] == "SUCCESS"
    assert len(calls) == 1
    assert calls[0]["block_number"] == 123456
    assert calls[0]["fee_on_transfer"] is True
    assert "PHASE15H_RUNTIME_SELL" in caplog.text
    assert "action=PARTIAL_TP1" in caplog.text
    assert "status=SUCCESS" in caplog.text

    skipped = _runtime_phase15h_sell_evidence(
        position={
            "id": 7,
            "token": "0x0000000000000000000000000000000000000002",
        },
        action="HOLD",
    )

    assert skipped is None
    assert len(calls) == 1


def test_paper_manager_attaches_phase15h_sell_after_close(monkeypatch):
    manager = PaperManager.__new__(PaperManager)

    class _Db:
        @staticmethod
        def open_positions():
            return [{
                "id": 9,
                "token": "0x0000000000000000000000000000000000000003",
            }]

    manager.db = _Db()
    manager.replay_closed_outcomes = lambda: None
    manager._process_position = lambda _pos: {
        "success": True,
        "source": "paper",
        "data": {
            "action": "CLOSE",
            "token": "0x0000000000000000000000000000000000000003",
            "status": "CLOSED",
        },
    }

    calls = []

    def fake_runtime_sell(*, position, action):
        calls.append((dict(position), action))
        return {
            "sell": {
                "contract": "phase15h_transaction_simulation_v1",
                "side": "SELL",
                "status": "SUCCESS",
            }
        }

    monkeypatch.setattr(
        manager_module,
        "_runtime_phase15h_sell_evidence",
        fake_runtime_sell,
    )

    result = manager.process()

    assert len(calls) == 1
    assert calls[0][0]["id"] == 9
    assert calls[0][1] == "CLOSE"
    assert (
        result[0]["data"]["phase15h_execution"]["sell"]["status"]
        == "SUCCESS"
    )
