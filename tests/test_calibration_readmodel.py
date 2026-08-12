from collections import deque

from app.learning.calibration_readmodel import (
    CalibrationReadModel,
    build_calibration_bucket,
    hot_path_contract,
)


def stats(
    fp=0.10,
    fn=0.10,
    confidence=0.80,
):
    return {
        "state": "CALIBRATION_READY",
        "sample_count": 100,
        "confidence": confidence,
        "false_positive_ratio": fp,
        "false_negative_ratio": fn,
        "avoided_loss_ratio": 0.2,
        "missed_opportunity_ratio": 0.1,
    }


def proposal(name="KEEP"):
    return {
        "proposal": name,
    }


def test_readmodel_uses_deque():
    r = CalibrationReadModel(2)
    assert isinstance(r._order, deque)


def test_store_and_get():
    r = CalibrationReadModel(2)

    out = r.put(
        "market",
        {"x": 1},
    )

    assert out["state"] == "STORED"

    got = r.get("market")

    assert got["state"] == "READY"
    assert got["payload"] == {"x": 1}


def test_fifo_eviction():
    r = CalibrationReadModel(2)

    r.put("a", {"x": 1})
    r.put("b", {"x": 2})
    r.put("c", {"x": 3})

    assert r.size == 2
    assert r.get("a")["state"] == "UNKNOWN"
    assert r.get("b")["state"] == "READY"
    assert r.get("c")["state"] == "READY"


def test_stale_is_not_ready():
    r = CalibrationReadModel(2)

    r.put("a", {"x": 1})

    assert (
        r.get(
            "a",
            freshness="STALE",
        )["state"]
        == "STALE"
    )


def test_stable_bucket():
    r = build_calibration_bucket(
        stats(),
        proposal(),
    )

    assert r[
        "calibration_bucket"
    ] == "STABLE"


def test_fp_pressure_bucket():
    r = build_calibration_bucket(
        stats(
            fp=0.50,
            fn=0.10,
        ),
        proposal(
            "DECREASE_WEIGHT_PROPOSAL"
        ),
    )

    assert r[
        "calibration_bucket"
    ] == "FP_PRESSURE"


def test_fn_pressure_bucket():
    r = build_calibration_bucket(
        stats(
            fp=0.10,
            fn=0.50,
        ),
        proposal(
            "INCREASE_WEIGHT_PROPOSAL"
        ),
    )

    assert r[
        "calibration_bucket"
    ] == "FN_PRESSURE"


def test_conflicted_bucket():
    r = build_calibration_bucket(
        stats(
            fp=0.50,
            fn=0.50,
        ),
        proposal("REVIEW"),
    )

    assert r[
        "calibration_bucket"
    ] == "CONFLICTED"


def test_low_confidence_bucket():
    r = build_calibration_bucket(
        stats(
            confidence=0.20,
        ),
        proposal("REVIEW"),
    )

    assert r[
        "calibration_bucket"
    ] == "LOW_CONFIDENCE"


def test_insufficient_stats_unknown_bucket():
    s = stats()
    s["state"] = "INSUFFICIENT_SAMPLE"

    r = build_calibration_bucket(
        s,
        proposal(
            "INSUFFICIENT_EVIDENCE"
        ),
    )

    assert r["state"] == "INSUFFICIENT"
    assert (
        r["calibration_bucket"]
        == "UNKNOWN"
    )


def test_stale_bucket_unknown():
    r = build_calibration_bucket(
        stats(),
        proposal(),
        freshness="STALE",
    )

    assert r["state"] == "UNKNOWN"


def test_hot_path_contract_forbids_heavy_work():
    r = hot_path_contract()

    assert (
        r["precomputed_readmodel_only"]
        is True
    )

    assert r["bounded_cache"] is True
    assert r["o1_eviction"] is True

    assert (
        r["raw_outcome_history_scan"]
        is False
    )

    assert r["db_aggregate"] is False
    assert r["graph_traversal"] is False
    assert r["ai_inference"] is False
    assert r["external_fetch"] is False
    assert r["provider_call"] is False

    assert (
        r[
            "automatic_calibration_apply"
        ]
        is False
    )


def test_authority_zero():
    r = build_calibration_bucket(
        stats(),
        proposal(),
    )

    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
