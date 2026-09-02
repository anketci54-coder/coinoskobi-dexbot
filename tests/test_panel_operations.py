from app.api.panel_operations import (
    build_operations_payload,
    build_vezir_context,
    exit_label,
    reason_label,
)


def test_panel_translates_technical_states_to_human_language():
    assert exit_label("DEFERRED") == "Doğrulama sırada"
    assert reason_label("PLAN_BLOCKED") == "İşlem şartları oluşmadı"


def test_operations_payload_has_single_human_facing_system_state():
    summary = build_operations_payload(
        runtime_active=True,
        data_healthy=False,
        watch={
            "open": 12,
            "closed": 0,
            "verified": 0,
            "limited": 2,
            "probed": 4,
        },
        paper={
            "open": 0,
            "closed": 18,
            "net_pnl_usdt": 4.2,
        },
        decisions=[
            {
                "reason": "PLAN_BLOCKED",
                "count": 10,
            }
        ],
    )

    assert summary["system"]["state"] == "DEGRADED"
    assert summary["system"]["label"] == "Sistem sınırlı veriyle çalışıyor"
    assert summary["presentation"]["technical_details_hidden"] is True
    assert summary["presentation"]["fabricated_values"] is False
    assert summary["main_reason"]["label"] == "İşlem şartları oluşmadı"


def test_operations_payload_reports_healthy_when_runtime_and_data_are_healthy():
    summary = build_operations_payload(
        runtime_active=True,
        data_healthy=True,
        watch={},
        paper={},
        decisions=[],
    )

    assert summary["system"]["state"] == "HEALTHY"
    assert summary["system"]["label"] == "Sistem çalışıyor"


def test_operations_payload_fails_safe_when_runtime_is_not_active():
    summary = build_operations_payload(
        runtime_active=False,
        data_healthy=True,
        watch={},
        paper={},
        decisions=[],
    )

    assert summary["system"]["state"] == "SAFE"
    assert summary["system"]["label"] == "Sistem güvenli beklemede"


def test_vezir_context_is_read_only_and_cannot_fabricate():
    operations = build_operations_payload(
        runtime_active=True,
        data_healthy=True,
        watch={},
        paper={},
        decisions=[],
    )

    context = build_vezir_context(operations)

    assert context["authority"] == "READ_ONLY"
    assert all(
        value is False
        for value in context["permissions"].values()
    )
    assert context["response_policy"]["technical_by_default"] is False
    assert context["response_policy"]["fabricate_missing_data"] is False
    assert context["response_policy"]["format"] == "ozet_neden_ne_yapmali"
