"""Candidate identity must survive discovery, revisit and admission."""
from types import SimpleNamespace
import sqlite3
import threading

import pytest

from app.analyzer import pair
from app.config.contracts import USDT
from app.pipeline import engine
from app.pipeline.fast_watch_revisit import FastWatchRevisitJob
from app.paper.database import PaperDatabase
from app.paper.schema import ensure_paper_schema

TOKEN = "0x" + "11" * 20
POOL = "0x" + "22" * 20
OTHER_POOL = "0x" + "33" * 20


@pytest.mark.parametrize("membership", ["VERIFIED", "FACTORY_MISMATCH", "UNKNOWN"])
def test_pipeline_uses_candidate_pool_not_token_wbnb_pool(monkeypatch, membership):
    pipeline = engine.PipelineEngine.__new__(engine.PipelineEngine)
    monkeypatch.setattr(engine, "token_analyze", lambda _: {
        "success": True, "data": {"name": "Token", "symbol": "T", "decimals": 18}})
    monkeypatch.setattr(engine, "pair_analyze", lambda _: {
        "success": True, "data": {"exists": True, "quote_ok": True, "pair": OTHER_POOL}})
    monkeypatch.setattr(pair, "verify_pair_membership", lambda *a, **k: {
        "state": membership, "pair": POOL, "token0": TOKEN, "token1": USDT.lower()},
        raising=False)
    monkeypatch.setattr(engine, "risk_analyze", lambda _: {"success": True, "data": {}})
    checked = []
    def sellability(token, *, pair):
        checked.append(pair.lower())
        return {"success": False, "data": {}}
    monkeypatch.setattr(engine, "sellability_analyze", sellability)
    result = pipeline.run(TOKEN, market_context={
        "candidate_pool": POOL, "candidate_quote_token": USDT,
        "candidate_dex": "pancakeswap_v2"})["data"]
    assert checked == ([POOL] if membership == "VERIFIED" else [])
    assert result["pair"].get("pair") == (POOL if membership == "VERIFIED" else None)
    assert result["paper"]["action"] != "PAPER_BUY"


@pytest.fixture
def lifecycle(monkeypatch):
    pipeline = engine.PipelineEngine.__new__(engine.PipelineEngine)
    db = object.__new__(PaperDatabase)
    db.conn = sqlite3.connect(":memory:")
    db.conn.row_factory = sqlite3.Row
    db._db_lock = threading.RLock()
    ensure_paper_schema(db.conn)
    pipeline.paper_db = db
    pipeline.observe_counterfactual_candidate = lambda *a, **k: None
    pipeline.cache = SimpleNamespace(all=lambda: [], history_for_pool=lambda *a, **k: [])
    pipeline._hybrid_exit_runtime_evidence = lambda *a, **k: {}
    pipeline.price = SimpleNamespace(get_price=lambda _: pytest.fail("Pair price must own entry"))
    state = {"prices": [1.0], "risk": {}, "sellable": True}
    monkeypatch.setattr(engine, "token_analyze", lambda _: {
        "success": True, "data": {"name": "Token", "symbol": "T", "decimals": 18}})
    monkeypatch.setattr(pair, "verify_pair_membership", lambda *a, **k: {
        "state": "VERIFIED", "pair": POOL})
    monkeypatch.setattr(engine, "risk_analyze", lambda _: {"success": True, "data": dict(state["risk"])})
    def sellability(token, *, pair):
        assert pair.lower() == POOL
        return {"success": True, "data": {
            "sellable": state["sellable"], "honeypot": False,
            "buy_tax": 0, "sell_tax": 0, "buy_gas": 0, "sell_gas": 0,
            "local_evidence": {"completed": True,
                "lp_security": {"lp_protected_fraction": 1.0},
                "exit_feasibility": {
                    "pair": POOL, "spot_price_series_usd": list(state["prices"]),
                    "runtime_spot_price_series_usd": list(state["prices"]),
                    "quote_reserve_usd": 50000, "latest_reserve_change_fraction": 0,
                    "route_friction_fraction": 0, "gas_price_wei": 0,
                    "wbnb_usd_estimate": 600}}}}
    monkeypatch.setattr(engine, "sellability_analyze", sellability)
    monkeypatch.setattr(engine, "_runtime_phase15h_buy_evidence", lambda **k: {"buy": {"status": "SUCCESS"}})
    monkeypatch.setattr("app.risk.paper_position_sizing._empirical_outcome_calibration", lambda **k: {
        "gap_multiplier": 1.0, "cost_uncertainty_fraction": 0.0,
        "account_risk_budget_fraction": .01, "gap_samples": 3,
        "cost_samples": 3, "account_risk_samples": 3})
    row = {"token": TOKEN, "pool": POOL, "quote_token": USDT,
           "dex": "pancakeswap_v2"}
    yield FastWatchRevisitJob(pipeline), state, row, db
    db.conn.close()


def test_fast_watch_matures_and_recomputes_admission_then_prevents_duplicate(lifecycle):
    job, state, row, db = lifecycle
    first = job._process(row)["data"]
    assert first["unified_score"]["opportunity_reason"] == "ACTIVE_PRICE_SERIES_NOT_READY"
    assert first["paper"]["action"] == "WATCH"
    state["prices"] = [1, 1.04, 1.02]
    second = job._process(row)["data"]
    assert second["unified_score"]["opportunity_reason"] == "ACTIVE_MOMENTUM_NOT_POSITIVE"
    assert second["paper"]["action"] == "WATCH"
    state["prices"] = [1, 1.04, 1.06]
    mature = job._process(row)["data"]
    assert mature["unified_score"]["opportunity_state"] == "HOT"
    assert mature["paper"]["action"] == "PAPER_BUY"
    assert db.open_positions()[0]["entry_price"] == 1.06
    assert job._process(row)["data"]["paper"]["reason"] == "OPEN_POSITION_EXISTS"
    assert len(db.open_positions()) == 1


@pytest.mark.parametrize("blocker", ["risk", "sellability", "quote", "size", "chase"])
def test_hot_evidence_cannot_bypass_canonical_gates(lifecycle, monkeypatch, blocker):
    job, state, row, db = lifecycle
    state["prices"] = [1, 1.04, 1.06]
    if blocker == "risk":
        state["risk"] = {"honeypot": True}
    elif blocker == "sellability":
        state["sellable"] = False
    elif blocker == "quote":
        from app.config.contracts import WBNB
        row["quote_token"] = WBNB
    else:
        original = engine.calculate_paper_position_size
        def blocked_size(**kw):
            result = original(**kw)
            if blocker == "size":
                result["entry_amount_usdt"] = 0
            else:
                result["blockers"] = ["ENTRY_ABOVE_CHASE_LIMIT"]
                result["immediate_entry_allowed"] = False
            return result
        monkeypatch.setattr(engine, "calculate_paper_position_size", blocked_size)
    result = job._process(row)["data"]
    assert result["paper"]["action"] != "PAPER_BUY"
    assert db.open_positions() == []


def test_partial_sales_and_final_residual_reconcile_in_sqlite(lifecycle):
    import json
    from app.paper.manager import PaperManager
    from app.strategy.mathematical_trade_plan import realization_values, exit_net_proceeds
    job, state, row, db = lifecycle
    state["prices"] = [1, 1.04, 1.06]
    assert job._process(row)["data"]["paper"]["action"] == "PAPER_BUY"
    initial = db.open_positions()[0]
    plan = json.loads(initial["mathematical_plan_json"])
    proceeds = 0
    sold = 0
    for stage, price, fraction in [("TP1", 1.2, .25), ("TP2", 1.3, .5)]:
        pos = db.open_positions()[0]
        sale = realization_values(token_amount=pos["token_amount"], fraction=fraction,
            current_price=price, remaining_cost_basis_usdt=pos["remaining_cost_basis_usdt"],
            cost_model=plan["cost_model"])
        assert db.apply_partial_realization(pos["id"], stage=stage, price=price,
                                            realization=sale, math_state_json="{}")
        proceeds += sale["net_proceeds_usdt"]
        sold += sale["sold_tokens"]
    residual = db.open_positions()[0]
    assert sold + residual["token_amount"] == pytest.approx(initial["initial_token_amount"])
    final_price = 1.1
    proceeds += exit_net_proceeds(residual["token_amount"], final_price, plan["cost_model"])
    manager = PaperManager.__new__(PaperManager)
    manager.db = db
    manager._observe_learning_outcome = lambda *a, **k: None
    manager._runtime_phase15h_sell_evidence = lambda *a, **k: {"sell": {"status": "SUCCESS"}}
    manager._close_math(residual, final_price, 1.3, 1.06, plan, "NORMAL_STOP_LOSS")
    closed = dict(db.conn.execute("select * from paper_trades where id=?", (initial["id"],)).fetchone())
    assert closed["status"] == "CLOSED"
    assert closed["token_amount"] == closed["remaining_cost_basis_usdt"] == 0
    assert closed["realized_proceeds_usdt"] == pytest.approx(proceeds)
    assert closed["net_pnl_usdt"] == pytest.approx(proceeds - initial["entry_amount_usdt"])
    assert closed["roi"] == pytest.approx(closed["net_pnl_usdt"] / initial["entry_amount_usdt"])
    assert closed["exit_price"] == final_price
