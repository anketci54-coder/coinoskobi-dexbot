from app.paper.trade_contract import (
    legacy_trade_contract,
    normalize_control_mode,
    normalize_trade_type,
)


def canonicalize_trade_axes(trade):
    value = dict(trade or {})

    explicit_control = str(
        value.get("control_mode") or ""
    ).strip()
    explicit_type = str(
        value.get("trade_type") or ""
    ).strip()

    control_mode = normalize_control_mode(
        explicit_control
    )
    trade_type = normalize_trade_type(
        explicit_type
    )

    if explicit_control and control_mode is None:
        raise ValueError("invalid control_mode")

    if explicit_type and trade_type is None:
        raise ValueError("invalid trade_type")

    legacy = legacy_trade_contract(
        value.get("trade_policy")
    )

    if control_mode is None and legacy is not None:
        control_mode = legacy["control_mode"]

    if trade_type is None and legacy is not None:
        trade_type = legacy["trade_type"]

    if control_mode is not None:
        value["control_mode"] = control_mode

    if trade_type is not None:
        value["trade_type"] = trade_type

    return value


def lifecycle_trade_type(position):
    value = dict(position or {})

    explicit = str(
        value.get("trade_type") or ""
    ).strip()

    trade_type = normalize_trade_type(explicit)

    if explicit:
        return trade_type

    legacy = legacy_trade_contract(
        value.get("trade_policy")
    )

    if legacy is None:
        return None

    return legacy["trade_type"]
