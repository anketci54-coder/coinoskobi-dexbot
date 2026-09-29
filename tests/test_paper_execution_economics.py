import copy
import json
import sqlite3
import threading

import pytest

from app.config.contracts import USDT
from app.dex.price_impact import constant_product_quote
from app.paper.database import PaperDatabase
from app.paper.execution_economics import paper_execution_fill
from app.paper.manager import PaperManager
from app.paper.schema import ensure_paper_schema
from app.pipeline.engine import PipelineEngine
from app.risk.paper_position_sizing import paper_available_capital_usdt


def context(price=1.0, drift=False):
    return {
        "quote_token": USDT, "token_decimals": 18, "quote_decimals": 18,
        "runtime_price_latest_block": 100, "wbnb_usd_estimate": 600,
        "implied_v2_fee_state": "READY", "implied_v2_fee_fraction": .0025,
        "reserve_samples": [
            {"block": 99, "token_reserve": 10000,
             "quote_reserve": 10000 * price * (1.01 if drift else 1)},
            {"block": 100, "token_reserve": 10000, "quote_reserve": 10000 * price},
        ],
    }


def execution(side, amount, ctx, *, transfer_retention=1.0):
    r = ctx["reserve_samples"][-1]
    output = constant_product_quote(
        reserve_in=r["quote_reserve"] if side == "BUY" else r["token_reserve"],
        reserve_out=r["token_reserve"] if side == "BUY" else r["quote_reserve"],
        amount_in=amount, fee_fraction=ctx["implied_v2_fee_fraction"],
    )["amount_out"] * transfer_retention
    return {
        "status": "SUCCESS", "quote_token": USDT,
        "block": {"number": 100, "chain_id": 56},
        "received_token_raw" if side == "BUY" else "received_quote_raw": int(output * 10**18),
        "recipient_balance_delta_raw": int(output * 10**18),
        "amount_in_usdt_raw": int(round(amount * 10**18)),
        "execution_gas_cost_wei": 200000 * 10**9,
        "raw": {
            "transaction": {"seed_quote_raw" if side == "BUY" else "seed_token_raw": int(round(amount * 10**18))},
            "receipt": {"status": "0x1", "gasUsed": hex(200000), "effectiveGasPrice": hex(10**9)},
            "approval_receipt": {"status": "0x1", "gasUsed": hex(45000), "effectiveGasPrice": hex(10**9)},
        },
    }


def fill(side="SELL", amount=100, ctx=None, proof=None):
    ctx = ctx or context(drift=True)
    proof = proof or execution(side, amount, ctx)
    return paper_execution_fill(side=side, execution=proof, context=ctx,
                                amount_in_raw=int(round(amount * 10**18)))


def test_receipt_gas_and_exact_impact_with_one_shared_mev_drift_reserve():
    value = fill()
    assert value["state"] == "BOUNDED"
    assert value["gas_usd"] == pytest.approx(.147)  # Swap AND approval.
    assert value["baseline_output_amount"] < 100 * .9975  # Size-dependent impact.
    reserve = value["adverse_execution_reserve_usd"]
    assert reserve > 0
    assert value["net_proceeds_usdt"] == pytest.approx(value["baseline_output_amount"] - reserve - .147)
    assert value["mev_expected_loss_usd"] is None
    assert value["fork_minout_enforced"] is False
    assert value["mev_and_natural_drift_are_additive"] is False


@pytest.mark.parametrize("defect,state", [
    ("gas", "UNKNOWN"), ("approval", "UNKNOWN"), ("native_price", "UNKNOWN"),
    ("nan_price", "UNKNOWN"), ("decimals", "UNKNOWN"), ("amount", "UNKNOWN"),
    ("block", "UNKNOWN"), ("delta", "UNKNOWN"), ("revert", "UNKNOWN"),
    ("history", "UNBOUNDED"), ("order", "UNBOUNDED"), ("fee", "UNBOUNDED"),
])
def test_missing_evidence_never_books_zero_cost(defect, state):
    ctx = context()
    proof = execution("SELL", 100, ctx)
    if defect == "gas":
        proof["raw"]["receipt"].pop("effectiveGasPrice")
    elif defect == "approval":
        proof["raw"].pop("approval_receipt")
    elif defect in {"native_price", "nan_price"}:
        ctx["wbnb_usd_estimate"] = None if defect == "native_price" else float("nan")
    elif defect == "decimals":
        ctx["quote_decimals"] = None
    elif defect == "amount":
        proof["raw"]["transaction"]["seed_token_raw"] += 1
    elif defect == "block":
        proof["block"]["number"] += 1
    elif defect == "delta":
        proof["recipient_balance_delta_raw"] += 1
    elif defect == "revert":
        proof["status"] = "REVERT"
    elif defect == "history":
        ctx["reserve_samples"] = ctx["reserve_samples"][-1:]
    elif defect == "order":
        ctx["reserve_samples"].reverse()
    elif defect == "fee":
        ctx["implied_v2_fee_state"] = "UNKNOWN"
    value = fill(ctx=ctx, proof=proof)
    assert value["state"] == state
    assert value["net_proceeds_usdt"] is None


def test_known_gas_can_exceed_exit_proceeds_without_clamping_loss():
    value = fill(amount=.001, ctx=context())
    assert value["state"] == "BOUNDED"
    assert value["net_proceeds_usdt"] < 0


def admitted_position():
    ctx = context()
    proof = execution("BUY", 100, ctx, transfer_retention=.97)
    buy_fill = fill("BUY", 100, ctx, proof)
    opening = {"execution_economics_v4": {"admission_enforced": True, "paper_buy_fill": buy_fill}}
    plan = {"contract": "mathematical_trade_plan", "entry": {"price": 1},
            "sl": {"initial_price": .90, "risk_log_distance": .1},
            "statistics": {"prices": [.98, 1., 1.02]},
            "cost_model": {"sell_retention_known": .9975, "sell_gas_usd": .001}}
    pos = {"token": "0x" + "11" * 20, "pool": "0x" + "22" * 20,
           "status": "OPEN", "trade_type": "NORMAL", "paper_account_version": "PAPER_10K_V2",
           "capital_before_usdt": 10000, "entry_amount_usdt": 100, "sl_price": .9,
           "math_state_json": "{}"}
    PipelineEngine._bind_paper_admission_price(pos, opening, plan, {}, 1.)
    pos["opening_context_json"] = json.dumps(opening)
    return pos, plan, buy_fill


def test_entry_tp1_runner_exit_reopen_and_capital_conserve(tmp_path, monkeypatch):
    import app.paper.manager as module
    pos, plan, buy_fill = admitted_position()
    assert pos["initial_token_amount"] == buy_fill["output_floor_amount"]
    assert pos["entry_amount_usdt"] == pytest.approx(100.147)
    assert pos["capital_after_entry_usdt"] == pytest.approx(9899.853)
    db = object.__new__(PaperDatabase)
    path = tmp_path / "paper.db"
    db.conn = sqlite3.connect(path)
    db.conn.row_factory = sqlite3.Row
    db._db_lock = threading.RLock()
    ensure_paper_schema(db.conn)
    db.insert(pos)
    manager = PaperManager.__new__(PaperManager)
    manager.db, manager.learning_feed, manager.hybrid_exit_evidence = db, None, None
    prices = {"current": 1.5}
    monkeypatch.setattr(module, "analyze_exit_feasibility", lambda *a: {"data": context(prices["current"], drift=True)})
    calls = []

    def sell(**kw):
        calls.append(kw)
        result = execution("SELL", kw["seed_token_raw"] / 10**18, context(prices["current"]))
        result["raw"]["transaction"]["seed_token_raw"] = kw["seed_token_raw"]
        return result

    monkeypatch.setattr(module, "simulate_paper_sell", sell)
    assert paper_available_capital_usdt(db.conn) == pytest.approx(9899.853)
    opened = db.open_positions()[0]
    tp1 = manager._process_normal_math_position(opened, 1.5, 1.5, 1., plan)["data"]
    assert tp1["action"] == "PARTIAL_TP1"
    remaining = db.open_positions()[0]
    sale = tp1["realization"]
    assert sale["sold_tokens"] + remaining["token_amount"] == pytest.approx(pos["initial_token_amount"])
    assert sale["realized_pnl_usdt"] >= json.loads(pos["math_state_json"])["initial_net_risk_usdt"] - 1e-9
    assert paper_available_capital_usdt(db.conn) == pytest.approx(9899.853 + sale["net_proceeds_usdt"])

    prices["current"] = 1.6
    hold = manager._process_normal_math_position(remaining, 1.6, 1.6, 1., plan)["data"]
    assert hold["action"] == "HOLD"
    remaining = db.open_positions()[0]
    assert remaining["runner_active"] == 1 and remaining["tp2_done"] == 0
    assert remaining["token_amount"] == pytest.approx(sale["remaining_tokens"])
    assert len(calls) == 2  # Full-size TP1 sizing proof and exact partial proof only.

    prices["current"] = 1.4
    closed = manager._process_normal_math_position(remaining, 1.4, 1.6, 1., plan)["data"]
    assert closed["action"] == "CLOSE"
    exit_fill = closed["phase15h_execution"]["sell"]["paper_fill"]
    expected_proceeds = sale["net_proceeds_usdt"] + exit_fill["net_proceeds_usdt"]
    expected_pnl = expected_proceeds - 100.147
    assert closed["net_pnl_usdt"] == pytest.approx(expected_pnl)
    assert paper_available_capital_usdt(db.conn) == pytest.approx(10000 + expected_pnl)
    db.conn.close()
    with sqlite3.connect(path) as conn:
        assert paper_available_capital_usdt(conn) == pytest.approx(10000 + expected_pnl)
        assert conn.execute("select count(*) from paper_realizations").fetchone()[0] == 1
        row = conn.execute("select token_amount, remaining_cost_basis_usdt, realized_proceeds_usdt from paper_trades").fetchone()
        assert row == pytest.approx((0, 0, expected_proceeds))


@pytest.mark.parametrize("state", ["UNKNOWN", "UNBOUNDED", "EDGE_BUDGET_EXCEEDED"])
def test_unbounded_final_sell_keeps_inventory_and_capital(state):
    from test_phase15h_paper_sell_runtime import _manager
    pos, plan, _ = admitted_position()
    manager = _manager()
    manager._runtime_phase15h_sell_evidence = lambda **kw: {
        "sell": {"status": "SUCCESS", "paper_fill": {"state": state, "net_proceeds_usdt": None}}
    }
    before = copy.deepcopy(pos)
    result = manager._close_math(pos, .8, 1., .8, plan, "NORMAL_STOP_LOSS")
    assert result["data"]["reason"] == "PAPER_SELL_ECONOMICS_NOT_BOUNDED"
    assert manager.db.closed == []
    assert pos == before


def test_tp1_viability_rejects_tiny_position_with_realistic_fixed_sell_gas():
    from app.strategy.mathematical_trade_plan import tp1_required_fraction
    fraction = tp1_required_fraction(
        token_amount=5212.348032750277,
        remaining_cost_basis_usdt=1.426422139281968,
        current_price=0.0002771,
        initial_risk_usdt=1.06843777759521,
        realized_pnl_usdt=0.0,
        cost_model={"sell_retention_known": 0.98, "sell_gas_usd": 0.25},
    )
    assert fraction is None


def test_tp1_viability_accepts_position_when_partial_can_recover_initial_risk():
    from app.strategy.mathematical_trade_plan import tp1_required_fraction
    fraction = tp1_required_fraction(
        token_amount=104016.50346709379,
        remaining_cost_basis_usdt=24.36368333622078,
        current_price=0.0002562,
        initial_risk_usdt=0.9406673320932626,
        realized_pnl_usdt=0.0,
        cost_model={"sell_retention_known": 0.987, "sell_gas_usd": 0.16},
    )
    assert fraction is not None
    assert 0.0 < fraction < 1.0
