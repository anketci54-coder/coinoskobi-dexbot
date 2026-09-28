"""Admission crosses the actual broker/parser/cache boundary after BUY proof."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.cache import gecko_cache
from app.market_data.broker import MarketDataBroker
from app.paper.cache_price import CachePrice
from app.risk import price_integrity as integrity
from app.scanner.followup_snapshot_cache import persist_registered_followup_snapshots
from app.universe.snapshot import DexScreenerSnapshotClient
from price_integrity_support import POOL, TOKEN, evidence
from test_paper_candidate_pool_binding import lifecycle
from test_paper_price_provenance_lifecycle import entry


@pytest.fixture
def provider(entry, monkeypatch, tmp_path):
    path = tmp_path / "cache.db"
    monkeypatch.setattr(gecko_cache, "DB", path)
    cache = gecko_cache.GeckoCache()
    cache.upsert_tracked_price(POOL, TOKEN, 1.06)
    reader = CachePrice(path)
    entry.job.pipeline.cache = cache
    payload = dict(chainId="bsc", pairAddress=POOL, dexId="pancakeswap",
                   baseToken={"address": TOKEN}, quoteToken={"address": integrity.USDT},
                   priceUsd="1.06")
    state = SimpleNamespace(payload=payload, unavailable=False, calls=[],
                            observed_at=datetime.now(timezone.utc).isoformat())

    def get(url, **kwargs):
        assert len(entry.buys) == 1
        assert url.endswith("/" + POOL)
        state.calls.append(url)
        if state.unavailable:
            raise ConnectionError("provider unavailable")
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"pairs": [state.payload]})

    client = DexScreenerSnapshotClient(session=SimpleNamespace(get=get),
                                      now_func=lambda: state.observed_at)
    fetch = client.fetch

    def checked_fetch(pools):
        # Admission remains on the caller thread; only the HTTP transport
        # moves to a cancellable reader. Keep SQLite ownership here.
        assert len(entry.buys) == 1
        assert entry.db.open_positions() == []
        return fetch(pools)

    monkeypatch.setattr(client, "fetch", checked_fetch)
    entry.job.pipeline.scanner = MarketDataBroker(snapshot_client=client)
    state.cache, state.reader = cache, reader
    yield state
    reader.db.close()
    cache.db.close()


@pytest.mark.parametrize("cached", ["numeric_only", "fresh", "wrong_identity"])
def test_buy_success_fetches_and_persists_exact_pool_envelope(entry, provider, cached):
    if cached != "numeric_only":
        old = evidence(1.06)
        if cached == "wrong_identity":
            old["base_token"] = "0x" + "33" * 20
        provider.cache.update_pool_price(POOL, 1.06, evidence=old)

    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert result["action"] == "PAPER_BUY"
    assert len(provider.calls) == 1
    stored = entry.db.open_positions()[0]
    opening = json.loads(stored["opening_context_json"])
    assert opening["admission_provenance"]["contract"] == "corrected_paper_v1"
    assert opening["admission_provenance"]["price_integrity"]["state"] == "VERIFIED_EXTREME"
    observed = opening["price_observation"]
    assert observed == provider.reader.get_observation(stored)
    assert observed["observed_at"] == provider.observed_at
    assert observed["price_usd"] == stored["entry_price"] == 1.06
    assert integrity.admission_check(stored)["state"] == "VERIFIED_EXTREME"
    assert all(opening[key] is False for key in (
        "decision_authority", "live_authority", "wallet_authority", "execution_authority"))


def test_entry_price_binds_to_new_observation_without_changing_quote_sizing(entry, provider, monkeypatch):
    from app.pipeline import engine
    from app.strategy.mathematical_trade_plan import buy_token_amount

    sizing_results = []
    original = engine.calculate_paper_position_size

    def size(**kwargs):
        result = original(**kwargs)
        sizing_results.append(dict(result))
        return result

    monkeypatch.setattr(engine, "calculate_paper_position_size", size)
    provider.payload["priceUsd"] = "1.0601"
    assert entry.job._process(entry.candidate)["data"]["paper"]["action"] == "PAPER_BUY"
    stored = entry.db.open_positions()[0]
    opening = json.loads(stored["opening_context_json"])
    plan = json.loads(stored["mathematical_plan_json"])
    assert len(sizing_results) == 1
    assert stored["entry_amount_usdt"] == sizing_results[0]["entry_amount_usdt"]
    assert stored["entry_price"] == opening["price_observation"]["price_usd"] == 1.0601
    assert plan["entry"]["price"] == stored["entry_price"]
    assert stored["token_amount"] == stored["initial_token_amount"] == pytest.approx(
        buy_token_amount(stored["entry_amount_usdt"], stored["entry_price"], plan["cost_model"]))


@pytest.mark.parametrize("defect", ["unavailable", "stale", "pool", "token", "quote", "chain"])
def test_buy_success_bad_fresh_fetch_never_inserts_even_with_valid_cache(entry, provider, defect):
    provider.cache.update_pool_price(POOL, 1.06, evidence=evidence(1.06))
    if defect == "unavailable":
        provider.unavailable = True
    elif defect == "stale":
        provider.observed_at = (datetime.now(timezone.utc) - timedelta(seconds=31)).isoformat()
    elif defect == "pool":
        provider.payload["pairAddress"] = "0x" + "33" * 20
    elif defect == "token":
        provider.payload["baseToken"]["address"] = "0x" + "33" * 20
    elif defect == "quote":
        from app.config.contracts import WBNB
        provider.payload["quoteToken"]["address"] = WBNB
    else:
        provider.payload["chainId"] = "ethereum"
    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert len(entry.buys) == len(provider.calls) == 1
    assert result["reason"] == "ENTRY_PRICE_NOT_PROVEN"
    assert entry.db.open_positions() == []


@pytest.mark.parametrize("missing_time", [False, True])
def test_followup_writer_atomically_replaces_price_and_envelope(provider, missing_time):
    cache = provider.cache
    cache.db.execute("CREATE TABLE candidate_followup_registry(pool, token, expires_at)")
    cache.db.execute("INSERT INTO candidate_followup_registry VALUES(?,?,?)", (POOL, TOKEN, 200))
    cache.db.commit()
    cache.update_pool_price(POOL, 1, evidence=evidence(1))
    fresh = evidence(1.06)
    if missing_time:
        fresh.pop("observed_at")
    result = persist_registered_followup_snapshots([fresh], db_path=gecko_cache.DB, now=100)
    assert result["updated"] == 1
    observed = provider.reader.get_observation({"pool": POOL})
    assert observed == integrity.observation(fresh)
    assert observed["observed_at"] == fresh.get("observed_at")
    assert integrity.observation_is_fresh(observed) is (not missing_time)


def test_watched_candidate_refresh_preserves_provider_envelope(provider, entry):
    from app.pipeline.engine import _runtime_watch_candidate

    fresh = evidence(1.061)
    provider.cache.db.execute("UPDATE gecko_pool_cache SET dex='pancakeswap_v2'")
    provider.cache.db.commit()
    pipeline = entry.job.pipeline

    def snapshots(pools, *, persist_followups):
        assert pools == [{"pool": POOL, "dex": "pancakeswap_v2"}]
        assert persist_followups is False
        return [fresh]

    pipeline.scanner = SimpleNamespace(scan=lambda: [], pool_snapshots=snapshots)
    _runtime_watch_candidate(TOKEN, POOL, enabled=True)
    try:
        assert pipeline.refresh_candidate_cache()["state"] == "REFRESHED"
        assert provider.reader.get_observation({"pool": POOL}) == integrity.observation(fresh)
    finally:
        _runtime_watch_candidate(TOKEN, POOL, enabled=False)


@pytest.mark.parametrize("status", ["UNKNOWN", "REVERT", None])
def test_failed_buy_does_not_fetch_or_insert(entry, provider, monkeypatch, status):
    from app.pipeline import engine

    monkeypatch.setattr(engine, "_runtime_phase15h_buy_evidence",
                        lambda **kw: {"buy": {"status": status}})
    assert entry.job._process(entry.candidate)["data"]["paper"]["reason"] == "PHASE15H_BUY_NOT_PROVEN"
    assert provider.calls == []
    assert entry.db.open_positions() == []


def test_cache_write_cannot_extend_admission_observation_lifetime(entry, provider, monkeypatch):
    now = datetime.fromisoformat(provider.observed_at)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(integrity, "datetime", Clock)
    writer = provider.cache.upsert_tracked_price

    def slow_writer(*args, **kwargs):
        nonlocal now
        result = writer(*args, **kwargs)
        now += timedelta(seconds=31)
        return result

    provider.cache.upsert_tracked_price = slow_writer
    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert len(provider.calls) == 1
    assert result["reason"] == "ENTRY_PRICE_NOT_PROVEN"
    assert entry.db.open_positions() == []


@pytest.mark.parametrize("price", ["1.10", "0.999"])
def test_new_price_still_obeys_original_entry_timing_limits(entry, provider, price):
    provider.payload["priceUsd"] = price
    result = entry.job._process(entry.candidate)["data"]["paper"]
    assert len(provider.calls) == 1
    assert result["reason"] == "ENTRY_PRICE_NOT_PROVEN"
    assert entry.db.open_positions() == []


def test_followup_write_failure_rolls_back_price_and_evidence(provider):
    cache = provider.cache
    cache.update_pool_price(POOL, 1, evidence=evidence(1))
    before = provider.reader.get_observation({"pool": POOL})
    cache.db.execute("CREATE TABLE candidate_followup_registry(pool, token, expires_at)")
    cache.db.execute("INSERT INTO candidate_followup_registry VALUES(?,?,?)", (POOL, TOKEN, 200))
    cache.db.execute("""CREATE TRIGGER reject_history BEFORE INSERT ON market_observation_history
                        BEGIN SELECT RAISE(ABORT, 'history failed'); END""")
    cache.db.commit()
    result = persist_registered_followup_snapshots([evidence(1.06)], db_path=gecko_cache.DB, now=100)
    assert result["state"] == "DB_ERROR"
    assert provider.reader.get_observation({"pool": POOL}) == before
