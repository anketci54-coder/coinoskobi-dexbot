RECENT_WINDOW = 50
MEDIUM_WINDOW = 200
LONG_WINDOW = 1000


def classify_window(age):
    age = _age(age)

    if age < RECENT_WINDOW:
        return "RECENT"

    if age < MEDIUM_WINDOW:
        return "MEDIUM"

    if age < LONG_WINDOW:
        return "LONG"

    return "ARCHIVAL"


def decay_outcome_weight(
    age,
    *,
    hard_evidence=False,
    same_regime=True,
    base_weight=1.0,
):
    base = _weight(base_weight)
    window = classify_window(age)

    if hard_evidence:
        weight = base
        decay_applied = False

    else:
        if window == "RECENT":
            factor = 1.0
        elif window == "MEDIUM":
            factor = 0.70
        elif window == "LONG":
            factor = 0.40
        else:
            factor = 0.15

        if not same_regime:
            factor *= 0.50

        weight = round(
            base * factor,
            6,
        )

        decay_applied = factor < 1.0

    return {
        "window": window,
        "age": _age(age),
        "hard_evidence": bool(
            hard_evidence
        ),
        "same_regime": bool(
            same_regime
        ),
        "base_weight": base,
        "effective_weight": weight,
        "decay_applied": decay_applied,
        "record_deleted": False,
        "hard_evidence_preserved": bool(
            hard_evidence
        ),
        "historical_record_preserved": True,
        "automatic_apply_allowed": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def build_evidence_window_summary(
    outcomes,
    current_regime=None,
):
    rows = list(outcomes or [])

    buckets = {
        "RECENT": 0,
        "MEDIUM": 0,
        "LONG": 0,
        "ARCHIVAL": 0,
    }

    hard_count = 0
    soft_count = 0
    total_effective_weight = 0.0

    for row in rows:
        row = dict(row or {})

        same_regime = (
            current_regime is None
            or row.get(
                "market_regime"
            ) is None
            or row.get(
                "market_regime"
            ) == current_regime
        )

        result = decay_outcome_weight(
            row.get(
                "age",
                0,
            ),
            hard_evidence=row.get(
                "hard_evidence",
                False,
            ),
            same_regime=same_regime,
            base_weight=row.get(
                "base_weight",
                1.0,
            ),
        )

        buckets[
            result["window"]
        ] += 1

        if result[
            "hard_evidence"
        ]:
            hard_count += 1
        else:
            soft_count += 1

        total_effective_weight += (
            result[
                "effective_weight"
            ]
        )

    return {
        "sample_count": len(rows),
        "window_counts": buckets,
        "hard_evidence_count": hard_count,
        "soft_evidence_count": soft_count,
        "total_effective_weight": round(
            total_effective_weight,
            6,
        ),
        "regime_aware": True,
        "soft_decay_enabled": True,
        "hard_evidence_preserved": True,
        "historical_records_deleted": False,
        "automatic_apply_allowed": False,
        "decision_authority": False,
        "execution_authority": False,
    }


def _age(value):
    try:
        return max(
            0,
            int(value),
        )
    except (TypeError, ValueError):
        return 0


def _weight(value):
    try:
        return max(
            0.0,
            float(value),
        )
    except (TypeError, ValueError):
        return 0.0
