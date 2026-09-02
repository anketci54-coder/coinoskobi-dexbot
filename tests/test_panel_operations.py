from app.api.panel_operations import (
    build_operations_summary,
    build_vezir_context,
    decision_message,
    provider_message,
    watch_exit_message,
)


def test_panel_translates_technical_states_to_human_language():
    assert provider_message("RATE_LIMIT") == "Veri saglayici kapasitesi dolu"
    assert watch_exit_message("DEFERRED") == "Cikis dogrulamasi sirada"
    assert decision_message("PLAN_BLOCKED") == "Islem sartlari olusmadi"


def test_operations_summary_has_single_human_facing_system_state():
    summary = build_operations_summary(
        runtime_active=True,
        provider_state="RATE_LIMIT",
        watch={"open": 12, "verified": 0, "limited": 2},
        paper={"open": 0, "closed": 18, "net_pnl_usdt": 4.2},
        radar={"cold": 20, "warm": 4, "hot": 1},
    )

    assert summary["system"]["mode"] == "DEGRADED"
    assert summary["data"]["label"] == "Veri saglayici kapasitesi dolu"
    assert summary["technical_details_hidden"] is True


def test_vezir_context_is_read_only_and_cannot_fabricate():
    operations = build_operations_summary(
        runtime_active=True,
        provider_state="HEALTHY",
    )
    context = build_vezir_context(
        operations=operations,
        freshness_seconds=8.0,
    )

    assert context["authority"] == "READ_ONLY"
    assert all(value is False for value in context["permissions"].values())
    assert context["response_policy"]["technical_by_default"] is False
    assert context["response_policy"]["fabricate_missing_data"] is False
    assert context["response_policy"]["prefer_summary_reason_action"] is True
