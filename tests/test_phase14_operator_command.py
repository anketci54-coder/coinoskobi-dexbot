from app.pipeline.operator_command import (
    build_operator_command,
)


def assert_authority_zero(command):
    assert command["executed"] is False
    assert (
        command[
            "automatic_apply_allowed"
        ]
        is False
    )
    assert (
        command["trade_authority"]
        is False
    )
    assert (
        command["live_authority"]
        is False
    )
    assert (
        command["wallet_authority"]
        is False
    )
    assert (
        command["signing_authority"]
        is False
    )
    assert (
        command["execution_authority"]
        is False
    )
    assert (
        command[
            "hardblock_override_authority"
        ]
        is False
    )


def ready_kwargs():
    return {
        "sellability": "SELLABILITY_OK",
        "liquidity_usd": 100000,
        "sl_tp_ready": True,
        "max_loss_ready": True,
        "daily_loss_cap_ready": True,
    }


def test_panel_buy_becomes_approval_request():
    command = build_operator_command(
        source="PANEL_OPERATOR",
        intent="BUY",
        token="0xabc",
        amount=0.1,
        amount_unit="BNB",
        requested_mode="MANUAL",
        **ready_kwargs(),
    )

    assert command["parsed_intent"] == "BUY"
    assert (
        command["command_state"]
        == "REQUIRES_APPROVAL"
    )
    assert (
        command["approval_required"]
        is True
    )
    assert command["amount"] == 0.1
    assert command["blocked_reasons"] == []

    assert_authority_zero(command)


def test_chat_buy_is_parsed_but_not_executed():
    command = build_operator_command(
        source="CHAT_OPERATOR",
        raw_input="BUY this token",
        token="0xabc",
        requested_mode="MANUAL",
        **ready_kwargs(),
    )

    assert command["source"] == "CHAT_OPERATOR"
    assert command["parsed_intent"] == "BUY"
    assert (
        command["command_state"]
        == "REQUIRES_APPROVAL"
    )
    assert (
        command["approval_required"]
        is True
    )

    assert_authority_zero(command)


def test_prepare_buy_is_prepared_not_executed():
    command = build_operator_command(
        source="CHAT_OPERATOR",
        raw_input="PREPARE BUY",
        token="0xabc",
        requested_mode="MANUAL",
        **ready_kwargs(),
    )

    assert (
        command["parsed_intent"]
        == "PREPARE_BUY"
    )
    assert (
        command["command_state"]
        == "PREPARED"
    )
    assert (
        command["approval_required"]
        is False
    )

    assert_authority_zero(command)


def test_hard_block_blocks_trade_request():
    command = build_operator_command(
        source="PANEL_OPERATOR",
        intent="BUY",
        token="0xabc",
        requested_mode="MANUAL",
        hard_block=True,
        **ready_kwargs(),
    )

    assert (
        command["command_state"]
        == "BLOCKED"
    )
    assert (
        "HARD_RISK_BLOCK"
        in command["blocked_reasons"]
    )

    assert_authority_zero(command)


def test_auto_mode_cannot_use_manual_command():
    command = build_operator_command(
        source="PANEL_OPERATOR",
        intent="BUY",
        token="0xabc",
        requested_mode="AUTO",
        **ready_kwargs(),
    )

    assert (
        command["command_state"]
        == "BLOCKED"
    )
    assert (
        "MANUAL_MODE_REQUIRED"
        in command["blocked_reasons"]
    )

    assert_authority_zero(command)


def test_emergency_stop_is_request_only():
    command = build_operator_command(
        source="PANEL_OPERATOR",
        intent="EMERGENCY_STOP",
        requested_mode="MANUAL",
    )

    assert (
        command["parsed_intent"]
        == "EMERGENCY_STOP"
    )
    assert (
        command["command_state"]
        == "PREPARED"
    )

    assert_authority_zero(command)


def test_unknown_chat_input_is_blocked():
    command = build_operator_command(
        source="CHAT_OPERATOR",
        raw_input="hello coinoskobi",
        requested_mode="MANUAL",
    )

    assert command["parsed_intent"] is None
    assert (
        command["command_state"]
        == "BLOCKED"
    )
    assert command["blocked_reasons"] == [
        "UNRECOGNIZED_INTENT"
    ]

    assert_authority_zero(command)


def test_cancel_is_canonical_cancelled_state():
    command = build_operator_command(
        source="CHAT_OPERATOR",
        raw_input="CANCEL",
        requested_mode="MANUAL",
    )

    assert (
        command["parsed_intent"]
        == "CANCEL"
    )
    assert (
        command["command_state"]
        == "CANCELLED"
    )

    assert_authority_zero(command)
