import app.risk.sellability as module


ADDRESS = (
    "0x790ad85a71b24cc795f2ee078cd86f4b285c7777"
)
PAIR = (
    "0x605a887ee2ed752a3265aa750019aef64fbfd09e"
)


def _local_complete():
    return {
        "completed": True,
        "lp_security": {
            "state": "PROTECTION_EVIDENCE_PRESENT",
            "lp_protected_fraction": 1.0,
        },
        "exit_feasibility": {
            "evidence_complete": True,
        },
        "lp_error": None,
        "exit_error": None,
    }


def test_goplus_payload_can_confirm_sellability():
    payload = {
        "code": 1,
        "message": "OK",
        "result": {
            ADDRESS.lower(): {
                "is_in_dex": "1",
                "is_honeypot": None,
                "cannot_buy": "0",
                "cannot_sell_all": "0",
                "buy_tax": "0",
                "sell_tax": "0.01",
                "is_open_source": "1",
            },
        },
    }

    data = module._parse_goplus_payload(
        payload,
        ADDRESS,
    )

    assert data["sellable"] is True
    assert data["honeypot"] is None
    assert data["buy_tax"] == 0.0
    assert data["sell_tax"] == 1.0


def test_goplus_missing_sell_all_proof_stays_unknown():
    payload = {
        "code": 1,
        "message": "OK",
        "result": {
            ADDRESS.lower(): {
                "is_in_dex": "1",
                "cannot_buy": "0",
                "cannot_sell_all": None,
                "buy_tax": "0",
                "sell_tax": "",
            },
        },
    }

    data = module._parse_goplus_payload(
        payload,
        ADDRESS,
    )

    assert data["sellable"] is None


def test_unknown_honeypot_uses_goplus_with_local_evidence(
    monkeypatch,
):
    primary = {
        "success": True,
        "provider_success": True,
        "provider_status_code": 200,
        "source": "sellability",
        "error": None,
        "data": {
            "sellable": None,
            "honeypot": None,
            "sellability_checked": True,
            "sellability_provider": "honeypot.is",
            "simulation_success": False,
            "simulation_error": "LIQ_SIM_FAILED",
            "local_evidence": _local_complete(),
        },
    }

    secondary = {
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
            "buy_tax": 0.0,
            "sell_tax": 1.0,
        },
    }

    monkeypatch.setattr(
        module,
        "_analyze_provider_once",
        lambda *args, **kwargs: primary,
    )
    monkeypatch.setattr(
        module,
        "_analyze_goplus_once",
        lambda *args, **kwargs: secondary,
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert result["data"]["sellable"] is True
    assert (
        result["data"]["provider_fallback_mode"]
        == "GOPLUS"
    )
    assert (
        result["data"]["local_evidence"]
        == _local_complete()
    )
    assert result["local_evidence_complete"] is True


def test_explicit_honeypot_is_never_overridden(
    monkeypatch,
):
    primary = {
        "success": True,
        "provider_success": True,
        "provider_status_code": 200,
        "source": "sellability",
        "error": None,
        "data": {
            "sellable": False,
            "honeypot": True,
            "sellability_checked": True,
            "sellability_provider": "honeypot.is",
            "local_evidence": _local_complete(),
        },
    }

    monkeypatch.setattr(
        module,
        "_analyze_provider_once",
        lambda *args, **kwargs: primary,
    )
    monkeypatch.setattr(
        module,
        "_analyze_goplus_once",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("GoPlus must not override Honeypot.is")
        ),
    )

    result = module.analyze(
        ADDRESS,
        pair=PAIR,
    )

    assert result["data"]["sellable"] is False
    assert result["data"]["honeypot"] is True
