import json
from collections import Counter


MULTIPLE_THRESHOLDS = (
    (1000.0, "1000X_PLUS"),
    (100.0, "100X_PLUS"),
    (10.0, "10X_PLUS"),
    (5.0, "5X_PLUS"),
    (2.0, "2X_PLUS"),
)


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _opening_context(row):
    evidence = row.get("evidence") or {}

    if not isinstance(evidence, dict):
        evidence = {}

    expected = evidence.get("expected_context")
    opening = (
        expected.get("opening_context")
        if isinstance(expected, dict)
        else None
    )

    if isinstance(opening, dict):
        return opening

    context = row.get("context")
    return context if isinstance(context, dict) else {}


def _counterfactual_context(row):
    context = row.get("context")

    if isinstance(context, dict):
        return context

    raw = row.get("context_json")

    if not raw:
        return {}

    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    return decoded if isinstance(decoded, dict) else {}


def _lifecycle(row):
    for key in (
        "lifecycle_snapshot",
        "lifecycle",
        "paper_lifecycle",
    ):
        value = row.get(key)
        if isinstance(value, dict):
            return value

    return {}


def _append_example(examples, value, max_examples):
    if len(examples) < max_examples:
        examples.append(value)


def _paper_forensics(rows, *, max_examples):
    causes = Counter()
    close_reasons = Counter()
    outcome_classes = Counter()
    signal_families = Counter()
    examples = []

    loss_count = 0
    win_count = 0
    flat_or_unknown_count = 0
    confirmed_profit_giveback_count = 0
    price_above_entry_then_loss_count = 0
    cost_drag_loss_count = 0
    no_upside_loss_count = 0
    lifecycle_evidence_count = 0

    for row in rows:
        realized_return = _number(
            row.get("realized_return")
        )
        entry_price = _number(row.get("entry_price"))
        exit_price = _number(row.get("exit_price"))
        lifecycle = _lifecycle(row)
        highest_price = _number(
            lifecycle.get("highest_price")
            if lifecycle.get("highest_price") is not None
            else row.get("highest_price")
        )
        peak_net_return = _number(
            lifecycle.get("peak_net_return")
        )
        gross_pnl_usdt = _number(
            lifecycle.get("gross_pnl_usdt")
            if lifecycle.get("gross_pnl_usdt") is not None
            else row.get("gross_pnl_usdt")
        )
        net_pnl_usdt = _number(
            lifecycle.get("net_pnl_usdt")
            if lifecycle.get("net_pnl_usdt") is not None
            else row.get("net_pnl_usdt")
        )
        generic_gross_pnl = _number(
            lifecycle.get("gross_pnl")
            if lifecycle.get("gross_pnl") is not None
            else row.get("gross_pnl")
        )
        generic_net_pnl = _number(
            lifecycle.get("net_pnl")
            if lifecycle.get("net_pnl") is not None
            else row.get("net_pnl")
        )
        pnl_currency = str(
            lifecycle.get("pnl_currency")
            or row.get("pnl_currency")
            or ""
        ).upper()

        if (
            gross_pnl_usdt is not None
            and net_pnl_usdt is not None
        ):
            gross_pnl = gross_pnl_usdt
            net_pnl = net_pnl_usdt
            analyzed_pnl_currency = "USDT"
        elif (
            generic_gross_pnl is not None
            and generic_net_pnl is not None
            and pnl_currency
        ):
            gross_pnl = generic_gross_pnl
            net_pnl = generic_net_pnl
            analyzed_pnl_currency = pnl_currency
        else:
            gross_pnl = None
            net_pnl = None
            analyzed_pnl_currency = None

        lifecycle_has_evidence = any(
            value is not None
            for value in (
                highest_price,
                _number(
                    lifecycle.get(
                        "lowest_price"
                    )
                    if lifecycle.get(
                        "lowest_price"
                    ) is not None
                    else row.get(
                        "lowest_price"
                    )
                ),
                peak_net_return,
                gross_pnl_usdt,
                net_pnl_usdt,
                generic_gross_pnl,
                generic_net_pnl,
            )
        )

        if lifecycle_has_evidence:
            lifecycle_evidence_count += 1

        classification = (
            row.get("classification") or {}
        ).get("outcome_class", "UNKNOWN")
        outcome_classes[str(classification)] += 1

        close_reason = str(
            row.get("close_reason") or "UNKNOWN"
        ).upper()
        close_reasons[close_reason] += 1

        opening = _opening_context(row)
        signal_attribution = opening.get(
            "signal_attribution"
        )

        if isinstance(signal_attribution, dict):
            for family, state in signal_attribution.items():
                signal_families[
                    f"{family}:{str(state).upper()}"
                ] += 1

        peak_price_return = None
        if (
            highest_price is not None
            and entry_price is not None
            and entry_price > 0
        ):
            peak_price_return = (
                highest_price / entry_price - 1.0
            )

        if realized_return is None:
            flat_or_unknown_count += 1
            cause = "OUTCOME_NOT_NUMERIC"

        elif realized_return > 0:
            win_count += 1
            cause = "REALIZED_WIN"

        elif realized_return == 0:
            flat_or_unknown_count += 1
            cause = "REALIZED_FLAT"

        else:
            loss_count += 1

            confirmed_profit_giveback = (
                peak_net_return is not None
                and peak_net_return > 0
            )
            price_above_entry_then_loss = (
                peak_price_return is not None
                and peak_price_return > 0
            )
            cost_drag_loss = (
                gross_pnl is not None
                and gross_pnl > 0
                and net_pnl is not None
                and net_pnl < 0
            )
            no_upside_loss = (
                peak_price_return is not None
                and peak_price_return <= 0
            )

            if confirmed_profit_giveback:
                confirmed_profit_giveback_count += 1
                cause = "CONFIRMED_PROFIT_GIVEBACK"

            elif cost_drag_loss:
                cost_drag_loss_count += 1
                cause = "COST_DRAG_LOSS"

            elif price_above_entry_then_loss:
                price_above_entry_then_loss_count += 1
                cause = "PRICE_UPSIDE_GIVEN_BACK"

            elif no_upside_loss:
                no_upside_loss_count += 1
                cause = "NO_UPSIDE_AFTER_ENTRY"

            elif str(classification) == "FALSE_POSITIVE":
                cause = "ENTRY_SIGNAL_FALSE_POSITIVE"

            else:
                cause = "REALIZED_LOSS_UNRESOLVED"

            _append_example(
                examples,
                {
                    "position_id": row.get("position_id"),
                    "token": row.get("token"),
                    "cause": cause,
                    "realized_return": realized_return,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "highest_price": highest_price,
                    "peak_price_return": peak_price_return,
                    "peak_net_return": peak_net_return,
                    "gross_pnl_usdt": gross_pnl_usdt,
                    "net_pnl_usdt": net_pnl_usdt,
                    "gross_pnl": generic_gross_pnl,
                    "net_pnl": generic_net_pnl,
                    "pnl_currency": analyzed_pnl_currency,
                    "close_reason": close_reason,
                },
                max_examples,
            )

        causes[cause] += 1

    return {
        "sample_count": len(rows),
        "win_count": win_count,
        "loss_count": loss_count,
        "flat_or_unknown_count": flat_or_unknown_count,
        "cause_counts": dict(causes),
        "close_reason_counts": dict(close_reasons),
        "outcome_class_counts": dict(outcome_classes),
        "entry_signal_state_counts": dict(signal_families),
        "confirmed_profit_giveback_count": (
            confirmed_profit_giveback_count
        ),
        "price_above_entry_then_loss_count": (
            price_above_entry_then_loss_count
        ),
        "cost_drag_loss_count": cost_drag_loss_count,
        "no_upside_loss_count": no_upside_loss_count,
        "lifecycle_evidence_count": lifecycle_evidence_count,
        "lifecycle_evidence_missing_count": (
            len(rows) - lifecycle_evidence_count
        ),
        "loss_examples": examples,
    }


def _multiple_for_row(row):
    entry = _number(row.get("entry_price"))
    maximum = _number(row.get("max_price"))

    if entry is not None and entry > 0 and maximum is not None:
        return maximum / entry

    realized_return = _number(row.get("realized_return"))

    if realized_return is not None:
        return max(0.0, 1.0 + realized_return)

    return None


def _multiple_bucket(row):
    explicit = (
        ("first_1000x_at", "1000X_PLUS"),
        ("first_100x_at", "100X_PLUS"),
        ("first_10x_at", "10X_PLUS"),
        ("first_5x_at", "5X_PLUS"),
        ("first_2x_at", "2X_PLUS"),
    )

    for field, bucket in explicit:
        if row.get(field) is not None:
            return bucket

    multiple = _multiple_for_row(row)

    if multiple is None:
        return "UNKNOWN"

    for threshold, bucket in MULTIPLE_THRESHOLDS:
        if multiple >= threshold:
            return bucket

    return "BELOW_2X"


def _blockers(context):
    values = []

    for key in ("plan_blockers", "sizing_blockers"):
        raw = context.get(key)
        if isinstance(raw, (list, tuple)):
            values.extend(
                str(value)
                for value in raw
                if value not in (None, "")
            )

    for key in (
        "reason",
        "opportunity_reason",
        "sizing_reason",
    ):
        value = context.get(key)
        if value not in (None, ""):
            values.append(str(value))

    sellability = context.get("sellability")
    if sellability not in (None, "", "SELLABILITY_OK"):
        values.append(str(sellability))

    return values


def _decision_identity(row):
    token = str(row.get("token") or "").strip().lower()
    pool = str(row.get("pool") or "").strip().lower()
    observed_at = row.get("observed_at")

    if token or pool or observed_at is not None:
        return (token, pool, observed_at)

    decision_id = row.get("decision_history_id")
    if decision_id is not None:
        return ("decision_history_id", decision_id)

    classification = (
        row.get("classification") or {}
    )

    context = _counterfactual_context(row)

    return (
        "content",
        str(
            classification.get(
                "outcome_class"
            )
            or ""
        ).upper(),
        str(
            row.get(
                "signal_state"
            )
            or ""
        ).upper(),
        str(
            row.get(
                "candidate_action"
            )
            or ""
        ).upper(),
        _number(
            row.get(
                "entry_price"
            )
        ),
        _number(
            row.get(
                "max_price"
            )
        ),
        _number(
            row.get(
                "realized_return"
            )
        ),
        json.dumps(
            context,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ),
    )


def _missed_opportunity_forensics(
    counterfactual_rows,
    durable_rows,
    *,
    max_examples,
):
    blockers = Counter()
    multiples = Counter()
    examples = []
    seen = set()
    missed_count = 0

    # Durable Phase 13C rows carry the longest observed horizon and
    # therefore win when the same decision is also present in the
    # short-horizon in-memory outcome channel.
    rows = []
    rows.extend(durable_rows)
    rows.extend(counterfactual_rows)

    for row in rows:
        classification = (
            row.get("classification") or {}
        ).get("outcome_class")

        candidate_action = str(
            row.get("candidate_action") or ""
        ).upper()
        signal_state = str(
            row.get("signal_state") or ""
        ).upper()

        # Durable rows do not carry the short-horizon classification
        # object. Only a POSITIVE non-entry is a missed-opportunity
        # fallback. NEGATIVE blocked/rejected upward outcomes retain
        # the canonical FALSE_NEGATIVE meaning and are not counted here.
        is_durable_missed_candidate = (
            classification is None
            and candidate_action in {
                "WATCH",
                "DOWNGRADE",
                "BLOCK",
                "REJECT",
            }
            and signal_state == "POSITIVE"
        )

        if (
            classification != "MISSED_OPPORTUNITY"
            and not is_durable_missed_candidate
        ):
            continue

        bucket = _multiple_bucket(row)

        if bucket in {"UNKNOWN", "BELOW_2X"}:
            if classification != "MISSED_OPPORTUNITY":
                continue

        key = _decision_identity(row)

        if key in seen:
            continue

        seen.add(key)

        missed_count += 1
        multiples[bucket] += 1

        context = _counterfactual_context(row)
        row_blockers = _blockers(context)

        for blocker in row_blockers:
            blockers[blocker] += 1

        _append_example(
            examples,
            {
                "token": row.get("token"),
                "pool": row.get("pool"),
                "multiple_bucket": bucket,
                "max_multiple": _multiple_for_row(row),
                "candidate_action": candidate_action,
                "signal_state": signal_state,
                "blockers": row_blockers,
            },
            max_examples,
        )

    return {
        "sample_count": missed_count,
        "multiple_counts": dict(multiples),
        "blocker_counts": dict(blockers),
        "examples": examples,
    }


def build_outcome_forensics(
    *,
    paper_events,
    counterfactual_events,
    durable_counterfactual_events=None,
    max_examples=20,
):
    paper_rows = list(paper_events)
    counterfactual_rows = list(counterfactual_events)
    durable_rows = list(
        durable_counterfactual_events or []
    )
    max_examples = max(1, min(100, int(max_examples)))

    paper = _paper_forensics(
        paper_rows,
        max_examples=max_examples,
    )
    missed = _missed_opportunity_forensics(
        counterfactual_rows,
        durable_rows,
        max_examples=max_examples,
    )

    evidence_count = (
        paper["sample_count"]
        + missed["sample_count"]
    )

    return {
        "state": (
            "READY"
            if evidence_count > 0
            else "INSUFFICIENT"
        ),
        "phase_owner": "13D",
        "paper": paper,
        "missed_opportunities": missed,
        "visible_evidence_count": evidence_count,
        "durable_counterfactual_event_count": len(
            durable_rows
        ),
        "profit_giveback_requires_peak_evidence": True,
        "cost_drag_requires_gross_and_net_evidence": True,
        "bounded": True,
        "max_examples": max_examples,
        "raw_db_scan": False,
        "external_fetch": False,
        "provider_call": False,
        "proposal_only": True,
        "automatic_apply_allowed": False,
        "config_write_allowed": False,
        "threshold_write_allowed": False,
        "weight_write_allowed": False,
        "strategy_rewrite_allowed": False,
        "hard_safety_weakening_allowed": False,
        "ai_authority": False,
        "trade_permission": False,
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
