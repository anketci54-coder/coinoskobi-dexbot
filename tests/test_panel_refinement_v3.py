import sqlite3
import time
from pathlib import Path

from app.api.panel_workspace_v3 import _rank_calendar_item, _rank_news_item, wallet_brief


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


def test_wallet_brief_falls_back_to_canonical_registry(tmp_path):
    db_path = tmp_path / "paper.db"
    con = sqlite3.connect(db_path)
    now = time.time()
    con.executescript(
        """
        CREATE TABLE wallet_discovery_registry(
            wallet_uid TEXT PRIMARY KEY,
            chain TEXT,
            address TEXT,
            first_seen_at REAL,
            last_seen_at REAL,
            discovery_source TEXT,
            freshness_state TEXT,
            lifecycle_state TEXT
        );
        CREATE TABLE wallet_success_score(
            wallet_uid TEXT PRIMARY KEY,
            calculated_at REAL,
            sample_depth INTEGER,
            consistency_score REAL,
            entry_quality_score REAL,
            exit_quality_score REAL,
            loss_control_score REAL,
            risk_adjusted_score REAL,
            freshness_score REAL,
            success_score REAL,
            qualification_state TEXT
        );
        """
    )
    rows = [
        ("bsc:0x" + "1" * 40, "0x" + "1" * 40, now - 20),
        ("bsc:0x" + "2" * 40, "0x" + "2" * 40, now - 10),
    ]
    con.executemany(
        """
        INSERT INTO wallet_discovery_registry(
            wallet_uid, chain, address, first_seen_at, last_seen_at,
            discovery_source, freshness_state, lifecycle_state
        ) VALUES(?, 'bsc', ?, ?, ?, 'TRANSACTION_FROM_ONLY', 'FRESH', 'ACTIVE')
        """,
        [(uid, address, seen, seen) for uid, address, seen in rows],
    )
    con.execute(
        """
        INSERT INTO wallet_success_score(
            wallet_uid, calculated_at, sample_depth, qualification_state
        ) VALUES(?, ?, 5, 'SUCCESSFUL')
        """,
        (rows[0][0], now),
    )
    con.commit()
    con.close()

    payload = wallet_brief(db_path)

    assert payload["available"] is True
    assert payload["candidates"] == 2
    assert payload["successful"] == 1
    assert payload["candidate_source"] == "REGISTRY"
    assert len(payload["rows"]) == 2
    assert {row["source"] for row in payload["rows"]} == {"TRANSACTION_FROM_ONLY"}
    assert payload["read_only"] is True
    assert payload["wallet_authority"] is False
    assert payload["execution_authority"] is False


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
