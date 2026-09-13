import json
import sqlite3

import pytest

from app.risk import paper_position_sizing as sizing


def _existing_db(path):
    sqlite3.connect(path).close()
    return path


def _valid_exclusion():
    return {
        "source_table": "paper_trades",
        "position_id": 37,
        "created_at": "2026-09-13T15:18:35.118255+00:00",
        "closed_at": "2026-09-13T16:25:18.506054+00:00",
        "reason": "BUG_CONTAMINATED_RUNTIME_LIFECYCLE_STARVATION_PR147",
    }


def _write(path, row):
    path.write_text(
        json.dumps({
            "version": 1,
            "exclusions": [row],
        }),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("source_table", 123),
        ("created_at", 1789320000),
        ("created_at", {"value": "bad"}),
        ("closed_at", 1789321000.5),
        ("closed_at", ["bad"]),
        ("position_id", True),
        ("position_id", 37.8),
        ("position_id", "37"),
    ],
)
def test_malformed_fingerprint_value_types_fail_closed(
    tmp_path,
    monkeypatch,
    key,
    value,
):
    db_path = _existing_db(tmp_path / "paper.db")
    registry_path = tmp_path / "exclusions.json"

    row = _valid_exclusion()
    row[key] = value
    _write(registry_path, row)

    monkeypatch.setattr(
        sizing,
        "PAPER_OUTCOME_EXCLUSIONS_PATH",
        registry_path,
    )

    calibration = sizing._empirical_outcome_calibration(
        str(db_path)
    )

    assert calibration["ready"] is False
    assert calibration["reason"] == "OUTCOME_EXCLUSION_REGISTRY_INVALID"
    assert calibration["gap_samples"] == 0
    assert calibration["account_risk_samples"] == 0
