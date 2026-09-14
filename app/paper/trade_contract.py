CONTROL_MODES = frozenset({
    "AUTO",
    "MANUAL",
})

TRADE_TYPES = frozenset({
    "NORMAL",
    "VUR_KAC",
})

LEVEL_SOURCES = frozenset({
    "SYSTEM",
    "USER_OVERRIDDEN",
})


LEGACY_TRADE_POLICY_MAP = {
    "NORMAL": {
        "control_mode": "AUTO",
        "trade_type": "NORMAL",
    },
    "VUR_KAC": {
        "control_mode": "AUTO",
        "trade_type": "VUR_KAC",
    },
    "MANUAL_PANEL": {
        "control_mode": "MANUAL",
        "trade_type": "NORMAL",
    },
}


def normalize_control_mode(value):
    normalized = str(value or "").strip().upper()
    return normalized if normalized in CONTROL_MODES else None


def normalize_trade_type(value):
    normalized = str(value or "").strip().upper()
    return normalized if normalized in TRADE_TYPES else None


def normalize_level_source(value):
    normalized = str(value or "").strip().upper()
    return normalized if normalized in LEVEL_SOURCES else None


def legacy_trade_contract(trade_policy):
    policy = str(trade_policy or "").strip().upper()
    mapped = LEGACY_TRADE_POLICY_MAP.get(policy)
    return dict(mapped) if mapped is not None else None
