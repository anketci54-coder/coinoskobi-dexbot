import json
import math
import sqlite3

import pytest

from app.learning.paper_outcome_integrity import (
    PaperOutcomeIntegrity,
    _valid_timestamp as learning_timestamp_valid,
)
from app.risk import paper_position_sizing as sizing
from app.risk.paper_position_sizing import (
    OutcomeExclusionRegistryError,
    _load_outcome_exclusions,
    _valid_timestamp as risk_timestamp_valid,
)


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-13T15:18:35+00:00",
        "2026-09-13T15:18:35.118255+00:00",
        "2026-09-13T18:18:35+03:00",
        "2026-09-13T15:18:35Z",
    ],
)
def test_canonical_aware_timestamps_are_accepted(value):
    assert risk_timestamp_valid(value) is True
    assert learning_timestamp_valid(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "not-a-date",
        "2026-09-13T15:18:35",
        "2026-09-13 15:18:35+00:00",
        "2026-09-13T15:18:35+00:00\x00",
        "2026-09-13T15:18:35+00:00junk",
        "2026-09-13T15:18:35.1234567+00:00",
        "2026-13-13T15:18:35+00:00",
        "2026-09-13T25:18:35+00:00",
        "2026-09-13T15:18:35+24:00",
        "2026-09-13T15:18:35-24:00",
        "2026-09-13T15:18:35+00:60",
        "2026-09-13T15:18:35+01:99",
    ],
)
def test_noncanonical_or_invalid_timestamps_fail_closed(value):
    assert risk_timestamp_valid(value) is False
    assert learning_timestamp_valid(value) is False


def _write_registry(path):
    path.write_text(
        json.dumps({
            "version": 1,
            "exclusions": [],
        }),
        encoding="utf-8",
    )
    return path


def _build_invalid_outcome_db(path):
    db = sqlite3.connect(path)
    db.execute(
        """
        CREATE TABLE paper_trades (
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            closed_at TEXT,
            status TEXT,
            entry_price REAL,
            current_price REAL,
            exit_price REAL,
            entry_amount_usdt REAL,
            mathematical_plan_json TEXT,
            math_state_json TEXT,
            gross_pnl_usdt REAL,
            net_pnl_usdt REAL,
            net_pnl REAL,
            paper_account_version TEXT,
            realized_pnl_usdt REAL DEFAULT 0,
            remaining_cost_basis_usdt REAL
        )
        """
    )
    db.execute(
        """
        INSERT INTO paper_trades(
            id, created_at, closed_at, status,
            entry_price, current_price, exit_price,
            entry_amount_usdt,
            mathematical_plan_json, math_state_json,
            gross_pnl_usdt, net_pnl_usdt, net_pnl,
            paper_account_version
        ) VALUES(
            1, 'bad', 'also-bad', 'CLOSED',
            10.0, 8.0, 8.0, 100.0,
            ?, ?, -20.0, -20.0, -20.0,
            'PAPER_10K_V2'
        )
        """,
        (
            json.dumps({"entry": {"band_low": 9.0}}),
            json.dumps({"last_stop": 9.0}),
        ),
    )
    db.commit()
    db.close()
    return path


def _bootstrap_plan():
    risk_log_distance = 0.20
    return {
        "paper_eligible": True,
        "capital": {
            "entry_amount_usdt": 1000.0,
            "available_usdt": 10000.0,
            "safe_quote_reserve_usd": 5000.0,
            "liquidity_capacity_source": "VERIFIED_LP_PROTECTION",
        },
        "expected": {
            "known_net_edge_fraction": 0.10,
            "full_net_edge_fraction": 0.10,
        },
        "cost_model": {
            "cost_complete": True,
        },
        "market_statistics": {
            "risk_log_distance": risk_log_distance,
        },
        "entry": {
            "price": 1.0,
        },
        "sl": {
            "initial_price": math.exp(-risk_log_distance),
        },
        "position": {},
    }


def test_malformed_suffix_invalidates_registry_in_both_consumers(tmp_path):
    path = tmp_path / "exclusions.json"
    path.write_text(
        json.dumps({
            "version": 1,
            "exclusions": [
                {
                    "source_table": "paper_trades",
                    "position_id": 37,
                    "created_at": "2026-09-13T15:18:35+00:00\x00",
                    "closed_at": "2026-09-13T16:25:18+00:00",
                    "reason": "BUG_CONTAMINATED",
                }
            ],
        }),
        encoding="utf-8",
    )

    with pytest.raises(OutcomeExclusionRegistryError):
        _load_outcome_exclusions(path)

    integrity = PaperOutcomeIntegrity(path)
    assert integrity.available is False
    assert integrity.reason == "OUTCOME_EXCLUSION_REGISTRY_INVALID"


def test_invalid_stored_outcome_fingerprint_fails_calibration_closed(
    tmp_path,
    monkeypatch,
):
    db_path = _build_invalid_outcome_db(tmp_path / "paper.db")
    registry = _write_registry(tmp_path / "exclusions.json")

    monkeypatch.setattr(
        sizing,
        "PAPER_OUTCOME_EXCLUSIONS_PATH",
        registry,
    )

    calibration = sizing._empirical_outcome_calibration(
        str(db_path)
    )

    assert calibration["ready"] is False
    assert calibration["reason"] == "OUTCOME_FINGERPRINT_INVALID"
    assert calibration["gap_samples"] == 0
    assert calibration["cost_samples"] == 0
    assert calibration["account_risk_samples"] == 0


def test_invalid_stored_outcome_fingerprint_cannot_bootstrap(
    tmp_path,
    monkeypatch,
):
    db_path = _build_invalid_outcome_db(tmp_path / "paper.db")
    registry = _write_registry(tmp_path / "exclusions.json")

    monkeypatch.setattr(
        sizing,
        "PAPER_OUTCOME_EXCLUSIONS_PATH",
        registry,
    )

    result = sizing.calculate_paper_position_size(
        mathematical_plan=_bootstrap_plan(),
        available_capital_usdt=10000.0,
        db_path=str(db_path),
    )

    assert result["entry_amount_usdt"] == 0.0
    assert result["risk_amount_usdt"] == 0.0
    assert "OUTCOME_FINGERPRINT_INVALID" in result["blockers"]
    assert result.get("paper_calibration_bootstrap") is not True
