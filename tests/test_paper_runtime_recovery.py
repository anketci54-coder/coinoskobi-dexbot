import math
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.paper.manager import PaperManager
from app.pipeline.engine import PipelineEngine
from app.risk import paper_position_sizing as sizing
from app.scanner.gecko_scanner import GeckoScanner
from app.strategy.mathematical_trade_plan import build_trade_plan
from app.dex.open_position_hot_path import process_hot_positions


@pytest.fixture
def calibrated(monkeypatch):
    monkeypatch.setattr(sizing, "_empirical_outcome_calibration", lambda **_: {
        "gap_multiplier": 3.0,
        "account_risk_budget_fraction": 0.005,
        "cost_uncertainty_fraction": 0.001,
        "gap_samples": 3, "cost_samples": 3,
    })


def plan(*, protected=0.0, state="HOT"):
    return build_trade_plan(
        entry_price=1.2, available_capital_usdt=10000.0,
        price_series=[1.0, 1.15, 1.10, 1.2],
        quote_reserve_usd=50000.0, lp_protected_fraction=protected,
        sellability_status="SELLABILITY_OK", trade_type="NORMAL",
        sellability_data={"buy_tax": 0, "sell_tax": 0, "buy_gas": 100000, "sell_gas": 100000},
        exit_evidence={
            "route_friction_fraction": 0.0025, "gas_price_wei": 1000000000,
            "wbnb_usd_estimate": 600.0,
            "observed_min_quote_reserve_usd": 48000.0,
            "reserve_observation_count": 4,
        },
        market_context={"opportunity": {"state": state}},
    )


@pytest.mark.parametrize("state", ["HOT", "WARM"])
def test_empirical_liquidity_sizes_for_total_loss_without_lp_protection(
    calibrated,
    state,
):
    p = plan(state=state)
    assert (
        p["capital"]["liquidity_capacity_source"]
        == "EMPIRICAL_RESERVE_FLOOR"
    )
    assert p["capital"]["entry_amount_usdt"] > 0

    r = sizing.calculate_paper_position_size(
        mathematical_plan=p
    )

    assert r["entry_amount_usdt"] > 0.0
    assert r["risk_amount_usdt"] == r["entry_amount_usdt"]
    assert r["tail_loss_fraction"] == 1.0
    assert r["liquidity_protection_unverified"] is True
    assert r.get("paper_calibration_bootstrap") is not True
    assert p["live_eligible"] is False
    assert p["execution_authority"] is False


def test_dust_lp_protection_is_not_economic_capacity(calibrated):
    p = plan(protected=1.8e-17)
    assert p["capital"]["verified_quote_reserve_usd"] == pytest.approx(
        50000 * 1.8e-17
    )
    assert (
        p["capital"]["liquidity_capacity_source"]
        == "EMPIRICAL_RESERVE_FLOOR"
    )

    r = sizing.calculate_paper_position_size(
        mathematical_plan=p
    )

    assert r["entry_amount_usdt"] > 0.0
    assert r["risk_amount_usdt"] == r["entry_amount_usdt"]
    assert r["tail_loss_fraction"] == 1.0
    assert r["liquidity_protection_unverified"] is True


def test_verified_lp_provenance_survives_nonpositive_edge(calibrated):
    p = build_trade_plan(
        entry_price=1.0,
        available_capital_usdt=10000.0,
        price_series=[1.2, 1.1, 1.0],
        quote_reserve_usd=50000.0,
        lp_protected_fraction=1.0,
        sellability_status="SELLABILITY_OK",
        trade_type="NORMAL",
        sellability_data={
            "buy_tax": 0,
            "sell_tax": 0,
            "buy_gas": 100000,
            "sell_gas": 100000,
        },
        exit_evidence={
            "route_friction_fraction": 0.0025,
            "gas_price_wei": 1000000000,
            "wbnb_usd_estimate": 600.0,
            "observed_min_quote_reserve_usd": 48000.0,
            "reserve_observation_count": 4,
        },
        market_context={
            "opportunity": {
                "state": "HOT",
                "catastrophic_reserve_collapse": False,
            }
        },
    )

    assert p["expected"]["known_net_edge_fraction"] <= 0
    assert (
        p["capital"]["liquidity_capacity_source"]
        == "VERIFIED_LP_PROTECTION"
    )

    r = sizing.calculate_paper_position_size(
        mathematical_plan=p
    )

    assert r["entry_amount_usdt"] == 0.0
    assert "NET_EDGE_NOT_POSITIVE" in r["blockers"]
    assert (
        "LP_WITHDRAWAL_PROTECTION_UNVERIFIED"
        not in r["blockers"]
    )


@pytest.mark.parametrize("gate", ["hard", "sellability", "collapse", "edge", "plan", "cold"])
def test_bootstrap_never_bypasses_real_gates(calibrated, gate):
    p = plan()
    if gate == "hard":
        p["hard_block"] = True
    elif gate == "sellability":
        p["sellability_status"] = "SELLABILITY_FAIL"
    elif gate == "collapse":
        p["market_context"]["opportunity"]["catastrophic_reserve_collapse"] = True
    elif gate == "edge":
        p["expected"]["known_net_edge_fraction"] = -0.01
    elif gate == "plan":
        p["blockers"] = ["SUSPICIOUS_VOLUME"]
    else:
        p["market_context"]["opportunity"]["state"] = "COLD"
    r = sizing.calculate_paper_position_size(mathematical_plan=p)
    assert r["entry_amount_usdt"] == 0
    assert r["blockers"]


def test_positive_but_gas_dominated_notional_is_rejected(calibrated):
    p = plan(protected=1.0)
    p["capital"]["safe_quote_reserve_usd"] = 0.001
    r = sizing.calculate_paper_position_size(mathematical_plan=p)
    assert r["entry_amount_usdt"] == 0
    assert "FIXED_COST_NET_EDGE_NOT_POSITIVE" in r["blockers"]


def test_large_kelly_plan_cannot_concentrate_account(calibrated):
    p = plan(protected=1.0)
    p["capital"]["entry_amount_usdt"] = 9000.0
    r = sizing.calculate_paper_position_size(mathematical_plan=p)
    assert 0 < r["entry_amount_usdt"] <= r["tail_risk_amount_cap_usdt"]
    assert r["risk_amount_usdt"] <= 50.0


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -1, 0, "bad"])
def test_missing_or_invalid_price_never_reaches_exit_logic(bad, caplog):
    m = PaperManager.__new__(PaperManager)
    m.price = type("Price", (), {"get_price": lambda _, token: bad})()
    assert m._process_position({"id": 1, "token": "token"}) is None
    assert "PAPER_PRICE_UNAVAILABLE" in caplog.text


def test_broken_position_does_not_starve_other_exits():
    m = PaperManager.__new__(PaperManager)
    m.replay_closed_outcomes = lambda: None
    m.db = type("DB", (), {"open_positions": lambda _: [{"id": 1}, {"id": 2}]})()
    def process(pos):
        if pos["id"] == 1:
            raise ValueError("invalid persisted state")
        return {"id": 2, "action": "CLOSE"}
    m._process_position = process
    assert m.process() == [{"id": 2, "action": "CLOSE"}]


def test_evicted_open_pool_refresh_uses_persisted_identity():
    e = PipelineEngine.__new__(PipelineEngine)
    row = {"token": "token", "pool": "pool", "dex": "pancakeswap_v2"}
    e.manager = type("Manager", (), {"db": type("DB", (), {"open_positions": lambda _: [row]})()})()
    inserted = []
    e.cache = type("Cache", (), {
        "update_pool_price": lambda *args: False,
        "upsert_tracked_price": lambda _, *args: inserted.append(args),
    })()
    def prices(_, identities):
        assert identities == [{"chain": "bsc", **row}]
        return {"pool": 0.75}
    e.scanner = type("Scanner", (), {"_market_data_broker": object(), "pool_prices": prices})()
    assert e.refresh_open_position_prices()["refreshed"] == 1
    assert inserted == [("pool", "token", 0.75)]


def test_startup_snapshot_request_never_serializes_identity_dict(monkeypatch):
    scanner = GeckoScanner()
    seen = []
    monkeypatch.setattr(scanner, "_pool_snapshots_gecko", lambda addresses: seen.extend(addresses) or [{"pool": "0xpool"}])
    scanner.pool_snapshots([{"pool": "0xpool", "dex": "pancakeswap_v2"}], persist_followups=False)
    assert seen == ["0xpool"]


@pytest.mark.parametrize("delayed", [False, True])
def test_cache_lock_snapshot_reaches_manager_without_faking_freshness(monkeypatch, delayed):
    e = PipelineEngine.__new__(PipelineEngine)
    position = {"id": 1, "token": "0xtoken", "pool": "0xpool", "dex": "pancakeswap_v2"}
    now = datetime.now(timezone.utc)
    class ObservationClock:
        @staticmethod
        def now(_):
            return now - timedelta(minutes=10) if delayed else now
    monkeypatch.setattr("app.pipeline.engine.datetime", ObservationClock)
    def locked(*_):
        raise sqlite3.OperationalError("database is locked")
    fallback = SimpleNamespace(get_price=lambda _: 999)
    e.manager = SimpleNamespace(
        db=SimpleNamespace(open_positions=lambda: [position]), price=fallback,
        process=lambda: [e.manager.price.get_price("0xtoken")],
    )
    e.cache = SimpleNamespace(update_pool_price=locked, all=lambda: [])
    e.scanner = SimpleNamespace(pool_prices=lambda _: {"0xpool": 0.75})
    refresh = e.refresh_open_position_prices()
    assert refresh["failed"] == 1
    assert refresh["refreshed"] == 0
    assert process_hot_positions(e, refreshed_rows=refresh["fallback_price_rows"]) == [None if delayed else 0.75]
    assert e.manager.price is fallback


@pytest.mark.parametrize("response", [None, [], "invalid"])
def test_invalid_provider_response_defers_to_checked_cache(response):
    e = PipelineEngine.__new__(PipelineEngine)
    e.manager = SimpleNamespace(db=SimpleNamespace(open_positions=lambda: [
        {"token": "0xtoken", "pool": "0xpool", "dex": "pancakeswap_v2"},
    ]))
    e.scanner = SimpleNamespace(pool_prices=lambda _: response)
    assert e.refresh_open_position_prices()["state"] == "FAILED_USING_CACHE"
