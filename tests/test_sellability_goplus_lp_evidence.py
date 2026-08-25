import app.risk.sellability as module


ADDRESS = (
    "0x790ad85a71b24cc795f2ee078cd86f4b285c7777"
)
PAIR = (
    "0x605a887ee2ed752a3265aa750019aef64fbfd09e"
)


def _local(*, protected=0.0, total_supply_raw=123 * 10**18):
    return {
        "completed": True,
        "lp_security": {
            "pair": PAIR,
            "state": (
                "PROTECTION_EVIDENCE_PRESENT"
                if protected > 0
                else "UNPROVEN"
            ),
            "protection_evidence_present": protected > 0,
            "total_supply_raw": total_supply_raw,
            "lp_protected_fraction": protected,
            "lp_withdrawable_fraction": 1.0 - protected,
        },
        "exit_feasibility": {
            "evidence_complete": True,
        },
        "lp_error": None,
        "exit_error": None,
    }


def _primary(*, sellable=True, protected=0.0):
    return {
        "success": True,
        "provider_success": True,
        "provider_status_code": 200,
        "source": "sellability",
        "error": None,
        "data": {
            "sellable": sellable,
            "honeypot": False if sellable is True else None,
            "sellability_checked": True,
            "sellability_provider": "honeypot.is",
            "local_evidence": _local(protected=protected),
        },
    }


def _secondary(*, raw=123 * 10**18, fraction=0.75):
    return {
        "success": True,
        "provider_success": True,
        "provider_status_code": 200,
        "source": "sellability",
        "error": None,
        "data": {
            "sellable": True,
            "honeypot": None,
            "sellability_checked": True,
            "sellability_provider": "goplus",
            "goplus_pair_in_dex": True,
            "goplus_lp_total_supply_raw": raw,
            "goplus_lp_locked_fraction_reported": fraction,
            "goplus_lp_locked_holder_count": 1,
        },
    }


def test_goplus_lp_lock_is_bound_to_pair_and_supply():
    payload = {
        "code": 1,
        "message": "OK",
        "result": {
            ADDRESS.lower(): {
                "is_in_dex": "1",
                "cannot_buy": "0",
                "cannot_sell_all": "0",
                "buy_tax": "0",
                "sell_tax": "0.01",
                "lp_total_supply": "123",
                "dex": [
                    {
                        "pair": PAIR,
                        "liquidity": "100000",
                    },
                ],
                "lp_holders": [
                    {
                        "address": (
                            "0x1111111111111111111111111111111111111111"
                        ),
                        "is_locked": "1",
                        "percent": "0.60",
                    },
                    {
                        "address": (
                            "0x2222222222222222222222222222222222222222"
                        ),
                        "is_locked": "1",
                        "percent": "0.15",
                    },
                    {
                        "address": (
                            "0x3333333333333333333333333333333333333333"
                        ),
                        "is_locked": "0",
                        "percent": "0.25",
                    },
                ],
            },
        },
    }

    data = module._parse_goplus_payload(
        payload,
        ADDRESS,
        pair=PAIR,
    )

    assert data["goplus_pair_in_dex"] is True
    assert data["goplus_lp_total_supply_raw"] == 123 * 10**18
    assert data["goplus_lp_locked_fraction_reported"] == 0.75
    assert data["goplus_lp_locked_holder_count"] == 2


def test_verified_goplus_lock_enriches_unprotected_local_lp(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_analyze_goplus_once",
        lambda *args, **kwargs: _secondary(),
    )

    result = module._with_goplus_fallback(
        ADDRESS,
        _primary(),
        pair=PAIR,
    )

    data = result["data"]
    lp = data["local_evidence"]["lp_security"]

    assert data["sellability_provider"] == "honeypot.is"
    assert data["sellable"] is True
    assert data["lp_evidence_fallback_mode"] == "GOPLUS"
    assert data["goplus_lp_protection_verified"] is True
    assert lp["lp_protected_fraction"] == 0.75
    assert lp["lp_withdrawable_fraction"] == 0.25
    assert lp["protection_evidence_present"] is True
    assert lp["state"] == "PROTECTION_EVIDENCE_PRESENT"
    assert lp["onchain_state"] == "UNPROVEN"
    assert lp["lp_protection_source"] == "GOPLUS_LOCKED_LP_HOLDERS"


def test_supply_mismatch_cannot_create_persistent_liquidity(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_analyze_goplus_once",
        lambda *args, **kwargs: _secondary(
            raw=999 * 10**18,
        ),
    )

    result = module._with_goplus_fallback(
        ADDRESS,
        _primary(),
        pair=PAIR,
    )

    data = result["data"]
    lp = data["local_evidence"]["lp_security"]

    assert data["goplus_lp_protection_verified"] is False
    assert lp["lp_protected_fraction"] == 0.0
    assert lp["state"] == "UNPROVEN"


def test_existing_onchain_protection_does_not_call_goplus(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_analyze_goplus_once",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("GoPlus LP evidence is unnecessary")
        ),
    )

    result = module._with_goplus_fallback(
        ADDRESS,
        _primary(protected=1.0),
        pair=PAIR,
    )

    assert (
        result["data"]["local_evidence"]["lp_security"]
        ["lp_protected_fraction"]
        == 1.0
    )
