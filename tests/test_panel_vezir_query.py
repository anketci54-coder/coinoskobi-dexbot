from app.api.panel_operations import answer_vezir_query


BASE = {
    "system": {
        "state": "DEGRADED",
        "label": "Sistem sınırlı veriyle çalışıyor",
    },
    "watch": {
        "open": 120,
        "closed": 0,
        "verified": 0,
        "limited": 0,
        "probed": 3,
    },
    "paper": {
        "open": 0,
        "closed": 18,
        "net_pnl_usdt": -10.5,
    },
    "main_reason": {
        "label": "İşlem şartları oluşmadı",
        "count": 44,
    },
}


def test_vezir_explains_no_trade_from_real_context():
    r = answer_vezir_query(
        "Neden işlem açmadık?",
        BASE,
    )

    assert r["intent"] == "WHY_NO_TRADE"
    assert "İşlem şartları oluşmadı" in r["answer"]
    assert "sınırlı veriyle" in r["answer"]


def test_vezir_risk_is_human_facing():
    r = answer_vezir_query(
        "Şu an en önemli risk ne?",
        BASE,
    )

    assert r["intent"] == "RISK"
    assert "veri akışının sınırlı" in r["answer"]


def test_vezir_watch_summary_uses_real_counts():
    r = answer_vezir_query(
        "WATCH durumu nedir?",
        BASE,
    )

    assert r["intent"] == "WATCH"
    assert "120 fırsat" in r["answer"]
    assert "3 kayıt" in r["answer"]


def test_vezir_permissions_are_always_false():
    r = answer_vezir_query(
        "Sistem durumu ne?",
        BASE,
    )

    assert r["authority"] == "READ_ONLY"
    assert all(
        value is False
        for value in r["permissions"].values()
    )


def test_vezir_does_not_expose_technical_detail_by_default():
    r = answer_vezir_query(
        "Sistem durumu ne?",
        BASE,
    )

    assert r["technical"] is None


def test_vezir_can_show_bounded_technical_summary_when_requested():
    r = answer_vezir_query(
        "Teknik detay ver, RPC durumu nedir?",
        BASE,
    )

    assert r["technical"] is not None
    assert "RPC" in r["technical"]


def test_vezir_turkish_capital_i_positions_intent():
    r = answer_vezir_query(
        "İşlemleri özetle",
        BASE,
    )

    assert r["intent"] == "POSITIONS"
    assert "18 işlem kapanmış" in r["answer"]
    assert "-10.50 USDT" in r["answer"]
