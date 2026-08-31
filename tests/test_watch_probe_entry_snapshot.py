from app.learning.watch_probe_entry_snapshot import (
    WatchProbeEntrySnapshotStore,
)


def test_entry_snapshot_captures_real_training_fields(tmp_path):
    store = WatchProbeEntrySnapshotStore(
        tmp_path / "paper.db"
    )

    context = {
        "market_context": {
            "liquidity_usd": 25000.0,
            "market_intelligence": {
                "volume_usd": 50000.0,
                "buys": 42,
                "participant_identity_coverage": 0.75,
            },
            "origin_participation": {
                "coverage": 0.5,
            },
            "runtime_market_flow": {
                "native_event_count": 12,
                "flow_intelligence": {
                    "coverage": 0.8,
                    "participant_identity_coverage": 0.6,
                },
                "stream_math": {
                    "state": "READY",
                    "price_log_return": 0.01,
                    "liquidity_log_change": -0.02,
                    "ewma": {
                        "ewma_volatility": 0.03,
                    },
                },
            },
        },
        "runtime_intelligence": {
            "market_quality": {
                "volume_turnover": 2.0,
                "liquidity_state": "STABLE",
                "market_evidence_ready": True,
                "participant_evidence_ready": False,
            },
            "market_regime": {
                "market_regime": "TRENDING",
            },
            "flow_confirmation": {
                "confirmation": "CONFIRMED",
            },
            "flow_quality": {
                "flow_quality": "GOOD",
            },
            "flow_divergence": {
                "divergence_state": "NONE",
            },
        },
    }

    result = store.capture(
        probe_id=1,
        decision_history_id=10,
        context=context,
        captured_at=1000.0,
    )

    assert result["stored"] is True

    row = store.snapshot(1)[0]

    assert row["probe_id"] == 1
    assert row["decision_history_id"] == 10
    assert row["liquidity_usd"] == 25000.0
    assert row["volume_usd"] == 50000.0
    assert row["volume_turnover"] == 2.0
    assert row["buys"] == 42
    assert row["volatility_state"] == "NONZERO"
    assert row["ewma_volatility"] == 0.03


def test_entry_snapshot_distinguishes_zero_from_unknown_volatility(tmp_path):
    store = WatchProbeEntrySnapshotStore(
        tmp_path / "paper.db"
    )

    zero_ctx = {
        "market_context": {
            "runtime_market_flow": {
                "stream_math": {
                    "ewma": {
                        "ewma_volatility": 0.0,
                    }
                }
            }
        }
    }

    unknown_ctx = {
        "market_context": {
            "runtime_market_flow": {
                "stream_math": {
                    "ewma": {
                        "ewma_volatility": None,
                    }
                }
            }
        }
    }

    store.capture(
        probe_id=1,
        decision_history_id=1,
        context=zero_ctx,
        captured_at=1000.0,
    )

    store.capture(
        probe_id=2,
        decision_history_id=2,
        context=unknown_ctx,
        captured_at=1001.0,
    )

    rows = {
        r["probe_id"]: r
        for r in store.snapshot(10)
    }

    assert rows[1]["volatility_state"] == "ZERO"
    assert rows[2]["volatility_state"] == "UNKNOWN"


def test_entry_snapshot_is_immutable_per_probe(tmp_path):
    store = WatchProbeEntrySnapshotStore(
        tmp_path / "paper.db"
    )

    first = store.capture(
        probe_id=1,
        decision_history_id=1,
        context={"score": 1},
        captured_at=1000.0,
    )

    second = store.capture(
        probe_id=1,
        decision_history_id=2,
        context={"score": 999},
        captured_at=2000.0,
    )

    assert first["stored"] is True
    assert second["state"] == "ALREADY_CAPTURED"

    row = store.snapshot(1)[0]

    assert row["decision_history_id"] == 1
    assert row["captured_at"] == 1000.0
