import json
from datetime import datetime
from pathlib import Path


PAPER_OUTCOME_EXCLUSIONS_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "paper_outcome_exclusions.json"
)

TRUSTED = "TRUSTED"
BUG_CONTAMINATED = "BUG_CONTAMINATED"
INTEGRITY_UNAVAILABLE = "INTEGRITY_UNAVAILABLE"

_ALLOWED_TABLES = {
    "paper_trades",
    "paper_trades_archive",
}


def _valid_timestamp(value):
    if not isinstance(value, str):
        return False

    value = value.strip()
    if not value:
        return False

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False

    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() is not None
    )


class PaperOutcomeIntegrity:
    """Fail-closed learning gate for audited paper outcomes."""

    def __init__(self, path=None):
        self.path = Path(
            path or PAPER_OUTCOME_EXCLUSIONS_PATH
        )
        self._state = INTEGRITY_UNAVAILABLE
        self._reason = "OUTCOME_EXCLUSION_REGISTRY_INVALID"
        self._exclusions = []
        self.reload()

    @property
    def state(self):
        return self._state

    @property
    def reason(self):
        return self._reason

    @property
    def available(self):
        return self._state != INTEGRITY_UNAVAILABLE

    def reload(self):
        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return self._invalidate()

        if (
            not isinstance(payload, dict)
            or payload.get("version") != 1
            or not isinstance(payload.get("exclusions"), list)
        ):
            return self._invalidate()

        exclusions = []
        seen = set()

        for raw in payload["exclusions"]:
            if not isinstance(raw, dict):
                return self._invalidate()

            required = {
                "source_table",
                "position_id",
                "created_at",
                "closed_at",
                "reason",
            }
            if not required.issubset(raw):
                return self._invalidate()

            source = raw.get("source_table")
            position_id = raw.get("position_id")
            created_at = raw.get("created_at")
            closed_at = raw.get("closed_at")
            reason = raw.get("reason")

            if (
                not isinstance(source, str)
                or source.strip() not in _ALLOWED_TABLES
                or isinstance(position_id, bool)
                or not isinstance(position_id, int)
                or position_id <= 0
                or not _valid_timestamp(created_at)
                or not _valid_timestamp(closed_at)
                or not isinstance(reason, str)
                or not reason.strip()
            ):
                return self._invalidate()

            fingerprint = (
                source.strip(),
                position_id,
                created_at.strip(),
                closed_at.strip(),
            )

            if fingerprint in seen:
                return self._invalidate()
            seen.add(fingerprint)

            exclusions.append({
                "source_table": fingerprint[0],
                "position_id": fingerprint[1],
                "created_at": fingerprint[2],
                "closed_at": fingerprint[3],
                "reason": reason.strip(),
            })

        self._exclusions = exclusions
        self._state = TRUSTED
        self._reason = "OUTCOME_INTEGRITY_READY"
        return self.status()

    def classify(
        self,
        *,
        source_table,
        position_id,
        created_at,
        closed_at,
    ):
        if not self.available:
            return self._classification(
                INTEGRITY_UNAVAILABLE,
                self._reason,
                False,
            )

        if (
            not isinstance(source_table, str)
            or source_table.strip() not in _ALLOWED_TABLES
            or isinstance(position_id, bool)
            or not isinstance(position_id, int)
            or position_id <= 0
            or not _valid_timestamp(created_at)
            or not _valid_timestamp(closed_at)
        ):
            return self._classification(
                INTEGRITY_UNAVAILABLE,
                "OUTCOME_FINGERPRINT_INVALID",
                False,
            )

        fingerprint = (
            source_table.strip(),
            position_id,
            created_at.strip(),
            closed_at.strip(),
        )

        for exclusion in self._exclusions:
            if (
                exclusion["source_table"] == fingerprint[0]
                and exclusion["position_id"] == fingerprint[1]
                and exclusion["created_at"] == fingerprint[2]
                and exclusion["closed_at"] == fingerprint[3]
            ):
                return self._classification(
                    BUG_CONTAMINATED,
                    exclusion["reason"],
                    False,
                )

        return self._classification(
            TRUSTED,
            "OUTCOME_INTEGRITY_TRUSTED",
            True,
        )

    def status(self):
        return {
            "state": self._state,
            "reason": self._reason,
            "exclusion_count": len(self._exclusions),
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    @staticmethod
    def _classification(state, reason, trusted):
        return {
            "state": state,
            "reason": reason,
            "trusted_for_learning": trusted,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def _invalidate(self):
        self._state = INTEGRITY_UNAVAILABLE
        self._reason = "OUTCOME_EXCLUSION_REGISTRY_INVALID"
        self._exclusions = []
        return self.status()
