from datetime import datetime, timezone
from uuid import uuid4


VALID_SOURCES = {
    "PANEL_OPERATOR",
    "CHAT_OPERATOR",
}

VALID_INTENTS = {
    "ANALYZE",
    "PREPARE_BUY",
    "PREPARE_SELL",
    "PREPARE_CLOSE",
    "BUY",
    "SELL",
    "CLOSE_POSITION",
    "CANCEL",
    "EMERGENCY_STOP",
}

PREPARE_INTENTS = {
    "ANALYZE",
    "PREPARE_BUY",
    "PREPARE_SELL",
    "PREPARE_CLOSE",
}

DIRECT_TRADE_INTENTS = {
    "BUY",
    "SELL",
    "CLOSE_POSITION",
}

CONTROL_INTENTS = {
    "CANCEL",
    "EMERGENCY_STOP",
}


def _utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def _normalize_optional_text(value):
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _normalize_amount(value):
    if value is None:
        return None

    amount = float(value)

    if amount <= 0:
        raise ValueError(
            "amount must be positive"
        )

    return amount


def _parse_chat_intent(raw_input):
    """
    Bounded deterministic parser.

    This is intentionally not AI inference.
    It only recognizes explicit command phrases.
    """

    text = str(
        raw_input or ""
    ).strip().upper()

    if not text:
        return None

    normalized = (
        text.replace("-", " ")
        .replace("_", " ")
    )

    words = set(
        normalized.split()
    )

    if (
        "EMERGENCY" in words
        and "STOP" in words
    ):
        return "EMERGENCY_STOP"

    if (
        "ACIL" in words
        and (
            "DUR" in words
            or "DURDUR" in words
        )
    ):
        return "EMERGENCY_STOP"

    if (
        "CANCEL" in words
        or "IPTAL" in words
    ):
        return "CANCEL"

    if (
        "ANALYZE" in words
        or "ANALIZ" in words
        or "ANALİZ" in words
    ):
        return "ANALYZE"

    if (
        "PREPARE" in words
        or "HAZIRLA" in words
    ):
        if (
            "BUY" in words
            or "AL" in words
            or "ALIM" in words
        ):
            return "PREPARE_BUY"

        if (
            "SELL" in words
            or "SAT" in words
            or "SATIS" in words
            or "SATIŞ" in words
        ):
            return "PREPARE_SELL"

        if (
            "CLOSE" in words
            or "KAPAT" in words
        ):
            return "PREPARE_CLOSE"

    if (
        "CLOSE" in words
        or "KAPAT" in words
    ):
        return "CLOSE_POSITION"

    if (
        "BUY" in words
        or "AL" in words
    ):
        return "BUY"

    if (
        "SELL" in words
        or "SAT" in words
    ):
        return "SELL"

    return None


def build_operator_command(
    *,
    source,
    intent=None,
    raw_input=None,
    token=None,
    pool=None,
    chain=None,
    amount=None,
    amount_unit=None,
    position_id=None,
    requested_mode="MANUAL",
    reason=None,
    hard_block=False,
    sellability=None,
    liquidity_usd=None,
    sl_tp_ready=False,
    max_loss_ready=False,
    daily_loss_cap_ready=False,
    kill_switch=False,
    command_id=None,
    created_at=None,
):
    """
    Phase 14 canonical operator-command producer.

    Produces a structured request only.

    It cannot:
    - execute a trade
    - sign a transaction
    - send a transaction
    - grant live authority
    - override a hard block
    """

    normalized_source = str(
        source or ""
    ).strip().upper()

    if normalized_source not in VALID_SOURCES:
        raise ValueError(
            "invalid operator command source"
        )

    parsed_intent = (
        str(intent).strip().upper()
        if intent is not None
        else None
    )

    if (
        parsed_intent is None
        and normalized_source
        == "CHAT_OPERATOR"
    ):
        parsed_intent = (
            _parse_chat_intent(
                raw_input
            )
        )

    if parsed_intent not in VALID_INTENTS:
        return {
            "contract": (
                "phase14_operator_command_v1"
            ),
            "command_id": (
                command_id
                or str(uuid4())
            ),
            "created_at": (
                created_at
                or _utc_now()
            ),
            "source": normalized_source,
            "raw_input": raw_input,
            "parsed_intent": None,
            "token": (
                _normalize_optional_text(
                    token
                )
            ),
            "pool": (
                _normalize_optional_text(
                    pool
                )
            ),
            "chain": (
                _normalize_optional_text(
                    chain
                )
            ),
            "amount": None,
            "amount_unit": (
                _normalize_optional_text(
                    amount_unit
                )
            ),
            "position_id": (
                _normalize_optional_text(
                    position_id
                )
            ),
            "requested_mode": str(
                requested_mode
                or "MANUAL"
            ).upper(),
            "reason": (
                _normalize_optional_text(
                    reason
                )
            ),
            "approval_required": False,
            "command_state": "BLOCKED",
            "blocked_reasons": [
                "UNRECOGNIZED_INTENT"
            ],
            "proposed_action": None,
            "executed": False,
            "automatic_apply_allowed": False,
            "hindsight_reconstructed": False,
            "provider_call": False,
            "external_fetch": False,
            "ai_inference": False,
            "hot_path_wait": False,
            "trade_authority": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
            "hardblock_override_authority": False,
        }

    normalized_amount = (
        _normalize_amount(amount)
    )

    normalized_mode = str(
        requested_mode or "MANUAL"
    ).strip().upper()

    blocked_reasons = []

    if normalized_mode != "MANUAL":
        blocked_reasons.append(
            "MANUAL_MODE_REQUIRED"
        )

    if kill_switch:
        blocked_reasons.append(
            "KILL_SWITCH_ACTIVE"
        )

    trade_like = (
        parsed_intent
        in DIRECT_TRADE_INTENTS
    )

    prepare_trade = (
        parsed_intent
        in {
            "PREPARE_BUY",
            "PREPARE_SELL",
            "PREPARE_CLOSE",
        }
    )

    if trade_like or prepare_trade:
        if hard_block:
            blocked_reasons.append(
                "HARD_RISK_BLOCK"
            )

        if sellability not in {
            None,
            "SELLABILITY_OK",
        }:
            blocked_reasons.append(
                "SELLABILITY_NOT_READY"
            )

        if (
            liquidity_usd is not None
            and float(liquidity_usd)
            <= 0
        ):
            blocked_reasons.append(
                "LIQUIDITY_NOT_READY"
            )

        if not sl_tp_ready:
            blocked_reasons.append(
                "SL_TP_NOT_READY"
            )

        if not max_loss_ready:
            blocked_reasons.append(
                "MAX_LOSS_NOT_READY"
            )

        if not daily_loss_cap_ready:
            blocked_reasons.append(
                "DAILY_LOSS_CAP_NOT_READY"
            )

    if parsed_intent in {
        "BUY",
        "PREPARE_BUY",
    }:
        if not _normalize_optional_text(
            token
        ):
            blocked_reasons.append(
                "TOKEN_REQUIRED"
            )

    if parsed_intent in {
        "SELL",
        "PREPARE_SELL",
        "CLOSE_POSITION",
        "PREPARE_CLOSE",
    }:
        if (
            not _normalize_optional_text(
                token
            )
            and not _normalize_optional_text(
                position_id
            )
        ):
            blocked_reasons.append(
                "TOKEN_OR_POSITION_REQUIRED"
            )

    if blocked_reasons:
        command_state = "BLOCKED"
    elif parsed_intent == "CANCEL":
        command_state = "CANCELLED"
    elif parsed_intent == "EMERGENCY_STOP":
        command_state = "PREPARED"
    elif parsed_intent in DIRECT_TRADE_INTENTS:
        command_state = (
            "REQUIRES_APPROVAL"
        )
    else:
        command_state = "PREPARED"

    approval_required = (
        parsed_intent
        in DIRECT_TRADE_INTENTS
    )

    return {
        "contract": (
            "phase14_operator_command_v1"
        ),
        "command_id": (
            command_id
            or str(uuid4())
        ),
        "created_at": (
            created_at
            or _utc_now()
        ),
        "source": normalized_source,
        "raw_input": raw_input,
        "parsed_intent": parsed_intent,
        "token": (
            _normalize_optional_text(
                token
            )
        ),
        "pool": (
            _normalize_optional_text(
                pool
            )
        ),
        "chain": (
            _normalize_optional_text(
                chain
            )
        ),
        "amount": normalized_amount,
        "amount_unit": (
            _normalize_optional_text(
                amount_unit
            )
        ),
        "position_id": (
            _normalize_optional_text(
                position_id
            )
        ),
        "requested_mode": normalized_mode,
        "reason": (
            _normalize_optional_text(
                reason
            )
        ),
        "approval_required": (
            approval_required
        ),
        "command_state": command_state,
        "blocked_reasons": (
            list(dict.fromkeys(
                blocked_reasons
            ))
        ),
        "proposed_action": (
            parsed_intent
        ),

        # Phase 14 constitutional boundary.
        "executed": False,
        "automatic_apply_allowed": False,
        "hindsight_reconstructed": False,

        # Hot-path / external-work boundary.
        "provider_call": False,
        "external_fetch": False,
        "ai_inference": False,
        "hot_path_wait": False,

        # Authority boundary.
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
        "hardblock_override_authority": False,
    }
