from pathlib import Path


PANEL = Path("app/api/static/index.html")


def test_premium_operations_terminal_readability_contract():
    html = PANEL.read_text(encoding="utf-8")

    assert "İŞLEM MERKEZİ" in html
    assert "UNIVERSE RADAR" in html
    assert "FIRSAT RADARI" in html
    assert "EDGE INTELLIGENCE" in html
    assert "MARKET STATE FLOW" in html
    assert "RUNTIME & PAPER LEDGER" in html
    assert "SIGNAL TIMELINE" in html
    assert "VEZİR" in html
    assert "SİSTEM SAĞLIĞI" in html
    assert "SİSTEM & İSTİHBARAT" in html

    assert "--text:#f6fbff" in html
    assert "--text-2:#d2e1e8" in html
    assert "--muted:#94a9b5" in html
    assert "--cold:#57b9ff" in html
    assert "--warm:#ff9f1a" in html
    assert "--hot:#ff4438" in html


def test_premium_operations_terminal_uses_dense_command_center_layout():
    html = PANEL.read_text(encoding="utf-8")

    assert ".content{display:grid;grid-template-columns:minmax(0,1fr) 430px" in html
    assert ".middle{display:grid;grid-template-columns:310px minmax(0,1fr) minmax(290px,.82fr)" in html
    assert ".timeline-track{display:grid;grid-template-columns:repeat(8,1fr)" in html
    assert "COLD → WARM" in html
    assert "WARM → HOT" in html
    assert "HOT → COLD" in html
    assert "WSS ATTACHED" in html
    assert "PAPER ENTRY" in html
    assert "30M OUTCOME" in html


def test_premium_operations_terminal_preserves_real_data_contracts():
    html = PANEL.read_text(encoding="utf-8")

    assert "getJson('/api/dashboard')" in html
    assert "getJson('/api/runtime-candidates')" in html
    assert "getJson('/api/authority')" in html
    assert "getJson('/api/universe-panel')" in html
    assert "state.universe=universe" in html
    assert "u.source||'UNIVERSE'" in html
    assert "sahte veri yok" in html
    assert "VERİ BAĞLI DEĞİL" in html
    assert "Sahte oran gösterilmez" in html
    assert "Sahte haber yok" in html
    assert "Sahte etkinlik yok" in html


def test_premium_operations_terminal_renders_real_seismic_states_and_filters():
    html = PANEL.read_text(encoding="utf-8")

    assert "SEISMIC STATE FEED:" in html
    assert 'id="coldCount">COLD —' in html
    assert 'id="warmCount">WARM —' in html
    assert 'id="hotCount">HOT —' in html
    assert 'data-filter="COLD"' in html
    assert 'data-filter="WARM"' in html
    assert 'data-filter="HOT"' in html
    assert ".state.cold" in html
    assert ".state.warm" in html
    assert ".state.hot" in html
    assert "COLD_TO_WARM" in html
    assert "WARM_TO_HOT" in html
    assert "HOT_TO_COLD" in html
    assert "OBSERVE · READ ONLY" in html


def test_premium_operations_terminal_wires_selected_seismic_evidence_into_edge():
    html = PANEL.read_text(encoding="utf-8")

    assert 'id="edgeScore"' in html
    assert 'id="edgeMove"' in html
    assert 'id="edgePriceZ"' in html
    assert 'id="edgeVolumeZ"' in html
    assert 'id="edgeTxnsZ"' in html
    assert 'id="edgeLiquidityRatio"' in html
    assert 'id="edgeEvidence"' in html
    assert 'id="edgeReason"' in html
    assert "r.seismic||{}" in html
    assert "s.previous_state" in html
    assert "s.next_state" in html
    assert "s.evidence_count" in html
    assert "s.reason" in html
    assert "SEISMIC SCORE · SEÇİLİ POOL" in html


def test_premium_operations_terminal_has_no_wallet_or_execution_authority():
    html = PANEL.read_text(encoding="utf-8")

    assert "CÜZDAN KAPALI" in html
    assert "READ ONLY" in html
    assert "LIVE EXECUTION" in html
    assert "WALLET AUTHORITY" in html

    forbidden = (
        "eth_requestAccounts",
        "wallet_switchEthereumChain",
        "eth_sendTransaction",
        "sendTransaction(",
        "connectWallet(",
    )

    for marker in forbidden:
        assert marker not in html


def test_unbound_research_sections_fail_closed_instead_of_fabricating_values():
    html = PANEL.read_text(encoding="utf-8")

    assert "RELATIVE ALPHA" in html
    assert "Araştırma sonucu backend'e publish edilmeden panel alpha üretmez." in html
    assert "Haber sağlayıcısı panel backend'ine bağlanmadı." in html
    assert "Ekonomik takvim kaynağı bağlı değil." in html


def test_phase9_wallet_detail_is_bound_to_real_intelligence_summary():
    html = PANEL.read_text(encoding="utf-8")

    assert 'id="walletDetailBody"' in html
    assert "wallet_details_json" in html
    assert "phase9WalletDetails" in html
    assert "phase9Seen" in html
    assert "successful_wallets" in html
    assert "Henüz gerçek Phase 9 wallet detayı yok" in html
    assert "PHASE 9 · READ ONLY" in html
    assert "<small>BAŞARILI</small>" in html
