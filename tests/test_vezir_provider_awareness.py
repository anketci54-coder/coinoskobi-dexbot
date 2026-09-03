from app.api.panel_operations import answer_vezir_query, build_operations_payload


def degraded_operations():
    return build_operations_payload(
        runtime_active=True,
        data_healthy=False,
        watch={"open": 3164, "closed": 0, "verified": 0, "limited": 0, "probed": 3164},
        paper={"open": 0, "closed": 0, "net_pnl_usdt": 0.0},
        decisions=[{"reason": "WATCH", "count": 200}],
    )


def test_operations_identifies_provider_degradation_explicitly():
    operations = degraded_operations()

    assert operations["system"]["state"] == "DEGRADED"
    assert operations["system"]["provider_problem"] is True
    assert operations["system"]["data_state"] == "PROVIDER_DEGRADED"
    assert "provider" in operations["system"]["data_label"].lower()


def test_vezir_says_provider_problem_when_asked_system_status():
    result = answer_vezir_query("Sistem çalışıyor mu?", degraded_operations())

    assert result["intent"] == "SYSTEM"
    assert "provider" in result["answer"].lower()
    assert result["evidence"]["provider_problem"] is True
    assert result["authority"] == "READ_ONLY"


def test_vezir_links_no_trade_to_provider_problem_when_degraded():
    result = answer_vezir_query("Neden işlem yok?", degraded_operations())

    assert result["intent"] == "WHY_NO_TRADE"
    assert "provider" in result["answer"].lower()
    assert "güvenilir" in result["answer"].lower()


def test_vezir_greeting_does_not_dump_operations_summary():
    result = answer_vezir_query("Selam", degraded_operations())

    assert result["intent"] == "GREETING"
    assert result["answer"].startswith("Selam")
    assert "3164" not in result["answer"]
    assert "USDT" not in result["answer"]


def test_vezir_technical_provider_answer_exposes_no_provider_url():
    result = answer_vezir_query("RPC provider teknik durum nedir?", degraded_operations())

    assert result["technical"] is not None
    assert "provider" in result["technical"].lower()
    assert "http://" not in result["technical"]
    assert "https://" not in result["technical"]
    assert all(value is False for value in result["permissions"].values())
