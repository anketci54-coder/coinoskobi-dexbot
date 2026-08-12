from app.learning.outcome_evidence import (
    build_outcome_evidence,
    same_outcome_identity,
)


def test_evidence_ready():
    r = build_outcome_evidence(
        "bsc", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
        expected_context={"direction": "BULL"},
        realized_outcome={"return": 0.05},
    )
    assert r["state"] == "EVIDENCE_READY"
    assert r["outcome_id"] == "bsc:obs-1"


def test_missing_outcome_pending_not_success():
    r = build_outcome_evidence(
        "bsc", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
        realized_outcome=None,
    )
    assert r["state"] == "PENDING_OUTCOME"
    assert r["missing_outcome_is_success"] is False
    assert r["missing_outcome_is_failure"] is False


def test_missing_identity_unknown():
    r = build_outcome_evidence(
        None, None,
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
    )
    assert r["state"] == "UNKNOWN"
    assert r["outcome_id"] is None


def test_missing_times_unknown():
    r = build_outcome_evidence(
        "bsc", "obs-1",
        None, None,
    )
    assert r["state"] == "UNKNOWN"


def test_stale_unknown():
    r = build_outcome_evidence(
        "bsc", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
        realized_outcome={"return": 0.05},
        freshness="STALE",
    )
    assert r["state"] == "UNKNOWN"


def test_zero_coverage_unknown():
    r = build_outcome_evidence(
        "bsc", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
        evidence_coverage=0,
    )
    assert r["state"] == "UNKNOWN"


def test_chain_aware_identity():
    a = build_outcome_evidence(
        "bsc", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
    )
    b = build_outcome_evidence(
        "eth", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
    )
    assert a["outcome_id"] != b["outcome_id"]
    assert same_outcome_identity(a, b) is False


def test_same_identity():
    a = build_outcome_evidence(
        "bsc", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
    )
    b = build_outcome_evidence(
        "bsc", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T10:00:00Z",
    )
    assert same_outcome_identity(a, b) is True


def test_hindsight_rewrite_forbidden():
    r = build_outcome_evidence(
        "bsc", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
    )
    assert r["hindsight_rewrite_allowed"] is False


def test_authority_zero():
    r = build_outcome_evidence(
        "bsc", "obs-1",
        "2026-08-12T08:00:00Z",
        "2026-08-12T09:00:00Z",
    )

    assert r["trade_permission"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
