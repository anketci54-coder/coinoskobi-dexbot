from collections import deque


class CalibrationReadModel:
    def __init__(self, max_entries=2048):
        self.max_entries = max(1, int(max_entries))
        self._data = {}
        self._order = deque()

    @property
    def size(self):
        return len(self._data)

    def put(self, key, payload):
        if not key:
            return {
                "state": "INVALID",
                "stored": False,
            }

        if (
            key not in self._data
            and self.size >= self.max_entries
        ):
            oldest = self._order.popleft()
            self._data.pop(oldest, None)

        if key not in self._data:
            self._order.append(key)

        self._data[key] = dict(payload or {})

        return {
            "state": "STORED",
            "stored": True,
            "size": self.size,
            "bounded": True,
            "o1_eviction": True,
            "decision_authority": False,
            "execution_authority": False,
        }

    def get(self, key, freshness="FRESH"):
        if freshness != "FRESH":
            return _out(
                "STALE",
                None,
            )

        payload = self._data.get(key)

        if payload is None:
            return _out(
                "UNKNOWN",
                None,
            )

        return _out(
            "READY",
            dict(payload),
        )


def build_calibration_bucket(
    statistics,
    proposal,
    *,
    freshness="FRESH",
):
    stats = dict(statistics or {})
    prop = dict(proposal or {})

    if freshness != "FRESH":
        state = "UNKNOWN"

    elif (
        stats.get("state")
        != "CALIBRATION_READY"
    ):
        state = "INSUFFICIENT"

    else:
        state = "READY"

    return {
        "state": state,
        "calibration_bucket": _bucket(
            stats
        ),
        "sample_count": stats.get(
            "sample_count",
            0,
        ),
        "confidence": stats.get(
            "confidence",
            0.0,
        ),
        "false_positive_ratio": stats.get(
            "false_positive_ratio"
        ),
        "false_negative_ratio": stats.get(
            "false_negative_ratio"
        ),
        "avoided_loss_ratio": stats.get(
            "avoided_loss_ratio"
        ),
        "missed_opportunity_ratio": stats.get(
            "missed_opportunity_ratio"
        ),
        "freshness": freshness,
        "proposal_state": prop.get(
            "proposal",
            "INSUFFICIENT_EVIDENCE",
        ),
        "precomputed_only": True,
        "raw_outcome_history_scan": False,
        "db_aggregate": False,
        "graph_traversal": False,
        "ai_inference": False,
        "external_fetch": False,
        "provider_call": False,
        "automatic_calibration_apply": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def hot_path_contract():
    return {
        "precomputed_readmodel_only": True,
        "bounded_cache": True,
        "o1_eviction": True,
        "raw_outcome_history_scan": False,
        "db_aggregate": False,
        "graph_traversal": False,
        "ai_inference": False,
        "external_fetch": False,
        "provider_call": False,
        "automatic_calibration_apply": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _bucket(stats):
    if (
        stats.get("state")
        != "CALIBRATION_READY"
    ):
        return "UNKNOWN"

    confidence = float(
        stats.get(
            "confidence",
            0.0,
        )
        or 0.0
    )

    fp = stats.get(
        "false_positive_ratio"
    )

    fn = stats.get(
        "false_negative_ratio"
    )

    if fp is None or fn is None:
        return "UNKNOWN"

    fp = float(fp)
    fn = float(fn)

    if confidence < 0.40:
        return "LOW_CONFIDENCE"

    if fp >= 0.35 and fn >= 0.35:
        return "CONFLICTED"

    if fp >= 0.35:
        return "FP_PRESSURE"

    if fn >= 0.35:
        return "FN_PRESSURE"

    return "STABLE"


def _out(state, payload):
    return {
        "state": state,
        "payload": payload,
        "decision_authority": False,
        "execution_authority": False,
    }
