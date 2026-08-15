from app.pipeline.operating_mode import (
    build_operating_mode_readmodel,
)


def test_default_mode_is_paper_and_authority_zero():
    result = build_operating_mode_readmodel()

    assert result["selected_mode"] == "PAPER"
    assert result["effective_mode"] == "PAPER"
    assert result["authority_ready"] is False
    assert result[
        "mode_selection_grants_authority"
    ] is False

    for field in (
        "trade_authority",
        "decision_authority",
        "paper_authority",
        "live_authority",
        "wallet_authority",
        "signing_authority",
        "execution_authority",
        "hardblock_override_authority",
    ):
        assert result[field] is False


def test_manual_exposes_controls_without_authority():
    result = build_operating_mode_readmodel(
        selected_mode="MANUAL",
        requested_by="PANEL_OPERATOR",
        sl_tp_ready=True,
        max_loss_ready=True,
        daily_loss_cap_ready=True,
    )

    assert result["selected_mode"] == "MANUAL"

    # Until later live-authority phases,
    # effective mode remains PAPER.
    assert result["effective_mode"] == "PAPER"

    controls = result["operator_controls"]

    assert controls[
        "manual_buy_available"
    ] is True

    assert controls[
        "manual_sell_available"
    ] is True

    assert controls[
        "close_position_available"
    ] is True

    assert result["chatbot"][
        "command_input_available"
    ] is True

    assert result["chatbot"][
        "execution_from_chat"
    ] is False

    assert result[
        "execution_authority"
    ] is False


def test_auto_request_cannot_open_authority():
    result = build_operating_mode_readmodel(
        selected_mode="AUTO",
        sl_tp_ready=True,
        max_loss_ready=True,
        daily_loss_cap_ready=True,
        live_ready=True,
        signing_ready=True,
        execution_ready=True,
    )

    assert result["selected_mode"] == "AUTO"
    assert result["effective_mode"] == "PAPER"

    assert result["automation"][
        "auto_requested"
    ] is True

    assert result["automation"][
        "auto_ready"
    ] is False

    assert result["authority_ready"] is False

    assert result[
        "live_authority"
    ] is False

    assert result[
        "signing_authority"
    ] is False

    assert result[
        "execution_authority"
    ] is False


def test_auto_reports_readiness_blockers():
    result = build_operating_mode_readmodel(
        selected_mode="AUTO",
        hard_block=True,
        sellability="SELLABILITY_BLOCKED",
        liquidity_usd=0,
        kill_switch=True,
    )

    blockers = set(
        result["automation"][
            "readiness_blockers"
        ]
    )

    assert "HARD_RISK_BLOCK" in blockers
    assert "SELLABILITY_NOT_READY" in blockers
    assert "LIQUIDITY_NOT_READY" in blockers
    assert "SL_TP_NOT_READY" in blockers
    assert "MAX_LOSS_NOT_READY" in blockers
    assert "DAILY_LOSS_CAP_NOT_READY" in blockers
    assert "KILL_SWITCH_ACTIVE" in blockers
    assert "LIVE_NOT_READY" in blockers
    assert "SIGNING_NOT_READY" in blockers
    assert "EXECUTION_NOT_READY" in blockers
