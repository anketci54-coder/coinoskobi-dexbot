import json

import pytest

from app.learning.paper_outcome_integrity import (
    PaperOutcomeIntegrity,
    _valid_timestamp as learning_timestamp_valid,
)
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
    ],
)
def test_noncanonical_or_invalid_timestamps_fail_closed(value):
    assert risk_timestamp_valid(value) is False
    assert learning_timestamp_valid(value) is False


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
