"""Replay Issue #208's measured provider facts through real durable storage."""
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.filter.ingress_gate import IngressGate
from app.learning.counterfactual_observation import CounterfactualObservationStore
from app.pipeline.fast_watch_revisit import FastWatchRevisitJob


TOKEN = "0x947efeba58873e0f771bfa5a31454af0e99556c1"
POOL = "0x20f1b5de3c0d874675022a6e92c7e097743b1aca"


@pytest.mark.parametrize("lane,reason,changes", [
    ("DEFER", "LOW_LIQUIDITY", {}),
    ("DEFER", "LOW_LIQUIDITY,LOW_VOLUME", {"volume_h24_usd": 0}),
    ("DROP", "STALE_CACHE", {"stale": True}),
    ("DROP", "UNSUPPORTED_DEX", {"dex": "unsupported", "price_usd": 0}),
])
def test_durable_ingress_denial_records_fresh_decision(
    tmp_path, monkeypatch, caplog, lane, reason, changes,
):
    store = CounterfactualObservationStore(db_path=tmp_path / "paper.db")
    before = store.record(
        token=TOKEN, pool=POOL, entry_price=5.509e-6,
        observed_at=time.time() - 120,
        signal_state="POSITIVE", candidate_action="DOWNGRADE",
        context={
            "strategy": "PAPER_BUY", "paper": "WATCH", "hard_block": False,
            "opportunity_state": "HOT",
            "opportunity_reason": "ACTIVE_CONTINUATION_READY",
            "sellability": "SELLABILITY_UNKNOWN",
            "market_context": {"candidate_dex": "pancakeswap_v2"},
        },
    )
    assert before["decision_id"] is not None
    calls = []
    observed_at = datetime.now(timezone.utc)
    if changes.get("stale"):
        observed_at -= timedelta(hours=1)
    # Exact-pool public response measured 2026-09-22 08:58 UTC. Only the
    # clock is refreshed; normalization and the ingress gate are real.
    snapshot = {
        "source": "dexscreener", "dex": "pancakeswap_v2",
        "pool": POOL, "base_token": TOKEN,
        "quote_token": "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",
        "price_usd": 5.962e-6, "liquidity_usd": 4.54,
        "volume_h24_usd": 5375.74, "buys_h24": 38,
        "sells_h24": 0, "fdv_usd": 57235.0,
        "observed_at": observed_at.isoformat(),
        **{k: v for k, v in changes.items() if k != "stale"},
    }

    def snapshots(pools, **kwargs):
        calls.append(pools)
        assert kwargs["persist_followups"] is False
        return [dict(snapshot)]

    def forbidden(*args, **kwargs):
        pytest.fail("Ingress denial must not reach analyzers, probes or PAPER")

    pipeline = SimpleNamespace(
        counterfactual_store=store,
        scanner=SimpleNamespace(pool_snapshots=snapshots),
        ingress_gate=IngressGate(),
        run=forbidden, observe_counterfactual_candidate=forbidden,
    )
    job = FastWatchRevisitJob(pipeline)
    monkeypatch.setattr(job, "_refresh_local_sellability_evidence", forbidden)
    for name in ("_hot_universe_identities", "_warm_universe_identities",
                 "_unseen_universe_identities"):
        monkeypatch.setattr(job, name, lambda: [])
    try:
        ready, movement = job._watched_identity_buckets()
        assert ready == [(TOKEN, POOL, "pancakeswap_v2")]
        assert movement == []
        with caplog.at_level("INFO"):
            status = job._run_cycle_sync()
        assert calls == [[{"pool": POOL, "dex": "pancakeswap_v2"}]]
        assert status["state"] == "NO_ACTIVE_WATCH_CANDIDATES"
        assert status["processed"] == status["paper_buys"] == 0
        rows = store._db.execute(
            "SELECT * FROM candidate_decision_history ORDER BY id"
        ).fetchall()
        assert len(rows) == 2, "Ingress silently discarded the durable HOT target"
        latest = rows[-1]
        assert latest["id"] > before["decision_id"]
        assert latest["token"] == TOKEN and latest["pool"] == POOL
        assert latest["reason"] == reason
        assert latest["decision_action"] == ("WATCH" if lane == "DEFER" else "REJECT")
        context = json.loads(latest["context_json"])
        assert context["sellability"] == "SELLABILITY_SKIPPED"
        assert context["ingress"]["lane"] == lane
        assert context["market_context"]["liquidity_usd"] == 4.54
        assert context["market_context"]["observed_at"] == snapshot["observed_at"]
        assert latest["observed_at"] > rows[0]["observed_at"]
        assert f"reason={reason}" in caplog.text
        assert "PHASE15H_RUNTIME_BUY" not in caplog.text
        # Existing transition dedup remains intact on a repeated observation.
        job._fresh_rows(ready)
        assert store._db.execute(
            "SELECT count(*) FROM candidate_decision_history"
        ).fetchone()[0] == 2
        # No probe/follow-up is created by the ingress-only history write.
        assert store._db.execute(
            "SELECT count(*) FROM counterfactual_observations"
        ).fetchone()[0] == 1
    finally:
        store._db.close()
