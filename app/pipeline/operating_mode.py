VALID_MODES = {
    "PAPER",
    "MANUAL",
    "AUTO",
}

DEFAULT_MODE = "PAPER"


def build_operating_mode_readmodel(
    *,
    selected_mode=None,
    requested_by=None,
    changed_at=None,
    hard_block=False,
    sellability=None,
    liquidity_usd=None,
    sl_tp_ready=False,
    max_loss_ready=False,
    daily_loss_cap_ready=False,
    kill_switch=False,
    live_ready=False,
    signing_ready=False,
    execution_ready=False,
):
    """
    Phase 14 operating-mode readmodel.

    A selected mode describes operator intent only.
    It never grants trade/sign/live/execution authority.
    """

    selected = str(
        selected_mode or DEFAULT_MODE
    ).upper()

    if selected not in VALID_MODES:
        selected = DEFAULT_MODE
        mode_state = "INVALID_MODE_FALLBACK"
    else:
        mode_state = "SELECTED"

    readiness_blockers = []

    if hard_block:
        readiness_blockers.append(
            "HARD_RISK_BLOCK"
        )

    if sellability not in {
        "SELLABILITY_OK",
        None,
    }:
        readiness_blockers.append(
            "SELLABILITY_NOT_READY"
        )

    if (
        liquidity_usd is not None
        and float(liquidity_usd) <= 0
    ):
        readiness_blockers.append(
            "LIQUIDITY_NOT_READY"
        )

    if not sl_tp_ready:
        readiness_blockers.append(
            "SL_TP_NOT_READY"
        )

    if not max_loss_ready:
        readiness_blockers.append(
            "MAX_LOSS_NOT_READY"
        )

    if not daily_loss_cap_ready:
        readiness_blockers.append(
            "DAILY_LOSS_CAP_NOT_READY"
        )

    if kill_switch:
        readiness_blockers.append(
            "KILL_SWITCH_ACTIVE"
        )

    if selected == "AUTO":
        if not live_ready:
            readiness_blockers.append(
                "LIVE_NOT_READY"
            )

        if not signing_ready:
            readiness_blockers.append(
                "SIGNING_NOT_READY"
            )

        if not execution_ready:
            readiness_blockers.append(
                "EXECUTION_NOT_READY"
            )

    authority_ready = False

    return {
        "contract": (
            "phase14_operating_mode_v1"
        ),

        "selected_mode": selected,

        # Phase 14 cannot elevate effective
        # authority beyond PAPER.
        "effective_mode": "PAPER",

        "mode_state": mode_state,
        "requested_by": requested_by,
        "changed_at": changed_at,

        "authority_ready": authority_ready,

        "operator_controls": {
            "manual_buy_available": (
                selected == "MANUAL"
            ),
            "manual_sell_available": (
                selected == "MANUAL"
            ),
            "close_position_available": (
                selected == "MANUAL"
            ),
            "emergency_stop_available": True,
        },

        "chatbot": {
            "command_input_available": (
                selected == "MANUAL"
            ),
            "allowed_intents": [
                "ANALYZE",
                "PREPARE_BUY",
                "PREPARE_SELL",
                "PREPARE_CLOSE",
                "CANCEL",
            ],
            "execution_from_chat": False,
            "signing_from_chat": False,
            "hardblock_override": False,
        },

        "automation": {
            "auto_requested": (
                selected == "AUTO"
            ),
            "auto_ready": False,
            "readiness_blockers": (
                readiness_blockers
            ),
        },

        "safety": {
            "hard_block": bool(hard_block),
            "sellability": sellability,
            "liquidity_usd": liquidity_usd,
            "sl_tp_ready": bool(
                sl_tp_ready
            ),
            "max_loss_ready": bool(
                max_loss_ready
            ),
            "daily_loss_cap_ready": bool(
                daily_loss_cap_ready
            ),
            "kill_switch": bool(
                kill_switch
            ),
        },

        "command_sources": [
            "PANEL_OPERATOR",
            "CHAT_OPERATOR",
        ],

        "mode_selection_grants_authority": False,
        "read_only": True,
        "hot_path_wait": False,
        "provider_call": False,
        "external_fetch": False,
        "ai_inference": False,

        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
        "hardblock_override_authority": False,
    }
