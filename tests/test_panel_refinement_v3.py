from pathlib import Path

from app.api.panel_workspace_v3 import _rank_calendar_item, _rank_news_item


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app" / "api" / "static" / "index.html"
CSS = ROOT / "app" / "api" / "static" / "panel-refinement-v3.css"
JS = ROOT / "app" / "api" / "static" / "panel-refinement-v3.js"
API_INIT = ROOT / "app" / "api" / "__init__.py"


def test_refined_panel_removes_watch_card_from_main_layout():
    html = HTML.read_text(encoding="utf-8")
    assert '<div class="title">1 USDT TESTLER</div>' not in html
    assert 'id="accountingButton"' in html
    assert 'AIRDROP / IDO / ICO' in html
    assert 'id="walletDetailButton"' in html
    assert 'panel-refinement-v3.css' in html
    assert 'panel-refinement-v3.js' in html


def test_refined_panel_routes_registered():
    source = API_INIT.read_text(encoding="utf-8")
    assert "register_panel_workspace_v3_routes" in source
    assert 'paper_db=_panel.PAPER_DB' in source


def test_launch_news_is_ranked_and_stays_advisory_only():
    row = _rank_news_item({
        "source": "TEST",
        "title": "Official airdrop claim window opens tomorrow",
        "url": "https://example.test/a",
    })
    assert row is not None
    assert row["event_type"] == "AIRDROP"
    assert row["launch_event"] is True
    assert row["state"] in {"WARM", "HOT"}
    assert row["trade_signal"] is False
    assert row["decision_authority"] is False


def test_high_impact_calendar_is_hot_and_low_impact_is_filtered():
    hot = _rank_calendar_item({
        "title": "CPI m/m",
        "country": "USD",
        "impact": "High",
        "date": "2026-09-05",
    })
    assert hot is not None
    assert hot["state"] == "HOT"
    assert "ENFLASYONU" in hot["title_tr"]

    cold = _rank_calendar_item({
        "title": "Minor survey",
        "country": "NZD",
        "impact": "Low",
    })
    assert cold is None


def test_watch_status_presentation_never_exposes_unverified_label():
    js = JS.read_text(encoding="utf-8")
    assert "function watchStatus" in js
    assert "UNVERIFIED" not in js
    assert "return 'KAPANDI'" in js
    assert "return 'AÇIK'" in js


def test_refinement_keeps_authority_boundaries():
    js = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "eth_sendRawTransaction" not in js
    assert "PRIVATE_KEY" not in js
    assert "WALLET_ADDRESS" not in js
    assert "confirmed:true" not in js.replace(" ", "")
    assert "font-smoothing" in css
