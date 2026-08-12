def event_identity(event):
    e = event or {}
    tx = e.get("transaction_hash")
    idx = e.get("log_index")

    if not tx or idx is None:
        return None

    return f"{tx}:{idx}"


def validate_event_integrity(
    event,
    seen=None,
    last_block=None,
    last_log_index=None,
):
    e = event or {}
    seen = set(seen or [])

    identity = event_identity(e)

    if not identity:
        return _out("REJECTED", "MISSING_IDENTITY", identity)

    # Reorg/removal must be classified before duplicate.
    # A previously accepted event can later be explicitly
    # removed by the provider and must generate retraction.
    if e.get("removed") is True:
        return _out("REMOVED", "REORG_REMOVED_LOG", identity)

    if identity in seen:
        return _out("DUPLICATE", "ALREADY_SEEN", identity)

    block = _hexint(e.get("block_number"))
    idx = _hexint(e.get("log_index"))

    if block is None or idx is None:
        return _out("REJECTED", "INVALID_ORDER_FIELDS", identity)

    if last_block is not None:
        lb = _hexint(last_block)
        li = _hexint(last_log_index)

        if lb is not None:
            if block < lb:
                return _out("OUT_OF_ORDER", "OLDER_BLOCK", identity)

            if block == lb and li is not None and idx < li:
                return _out("OUT_OF_ORDER", "LOWER_LOG_INDEX", identity)

    return _out("ACCEPTED", None, identity)


def _hexint(value):
    try:
        if isinstance(value, str):
            return int(value, 16) if value.startswith("0x") else int(value)
        return int(value)
    except (TypeError, ValueError):
        return None


def _out(state, reason, identity):
    return {
        "state": state,
        "reason": reason,
        "event_identity": identity,
        "decision_authority": False,
        "execution_authority": False,
    }
