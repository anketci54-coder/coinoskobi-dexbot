from pathlib import Path


PANEL = Path("app/api/static/index.html")


def html() -> str:
    return PANEL.read_text(encoding="utf-8")


def test_header_is_tall_enough_for_brand_and_metrics():
    source = html()

    assert "grid-template-rows:92px minmax(0,1fr) 34px" in source
    assert "İŞLEM<br>MERKEZİ" in source
    assert "white-space:normal" in source
    assert "BAKİYE" in source
    assert "GÜNLÜK PNL" in source
    assert "TOPLAM PNL" in source
    assert "AÇIK POZİSYON" in source
    assert "KULLANILAN RİSK" in source


def test_radar_center_replaces_duplicate_radar_title():
    source = html()

    assert "RADAR MERKEZİ" in source
    assert "UNIVERSE RADAR" not in source
    assert "FIRSAT RADARI" not in source


def test_radar_center_has_only_requested_market_columns():
    source = html()

    header = (
        '<div class="radar-grid"><span>STATE</span>'
        '<span>VARLIK / POOL</span><span>SCORE</span>'
        '<span>24H HACİM</span><span>FİYAT</span>'
        '<span>5M</span><span>LİKİDİTE</span></div>'
    )
    assert header in source
    assert "<span>DEX</span>" not in source
    assert "EVIDENCE / DURUM" not in source


def test_radar_center_filters_zero_score_and_sorts_descending_for_all_tabs():
    source = html()

    assert "n(r.seismic.score)>0" in source
    assert ".sort((a,b)=>n(b?.seismic?.score)-n(a?.seismic?.score))" in source
    assert 'data-filter="ALL"' in source
    assert 'data-filter="COLD"' in source
    assert 'data-filter="WARM"' in source
    assert 'data-filter="HOT"' in source
    assert "score > 0 hareketli pool yok" in source


def test_manual_buy_sell_controls_are_prepare_only_and_auto_disables_them():
    source = html()

    assert '>AL</button>' in source
    assert '>SAT</button>' in source
    assert "state.operatingMode!=='MANUAL'" in source
    assert "prepareManualAction" in source
    assert "execution/signing authority kapalı; emir gönderilmedi" in source

    forbidden = (
        "eth_requestAccounts",
        "wallet_switchEthereumChain",
        "eth_sendTransaction",
        "sendTransaction(",
        "connectWallet(",
        "signTransaction(",
    )
    for marker in forbidden:
        assert marker not in source


def test_large_low_value_panels_are_removed_from_rendered_panel():
    source = html()

    removed = (
        "SİSTEM & PAPER LEDGER",
        "SON SİNYALLER",
        "SIGNAL TIMELINE",
        "SİSTEM SAĞLIĞI",
        "SİSTEM & İSTİHBARAT",
    )
    for marker in removed:
        assert marker not in source


def test_edge_analysis_is_compact_but_keeps_real_selected_pool_evidence():
    source = html()

    assert "grid-template-rows:195px minmax(0,1fr)" in source
    assert 'id="edgeScore"' in source
    assert 'id="edgeMove"' in source
    assert 'id="edge5m"' in source
    assert 'id="edgeVolumeZ"' in source
    assert 'id="edgeEvidence"' in source
    assert 'id="edgeReason"' in source
    assert "r.seismic||{}" in source


def test_news_and_calendar_share_one_scrollable_news_panel():
    source = html()

    assert 'id="newsTitle">HABER AKIŞI (0)' in source
    assert 'id="newsStream"' in source
    assert 'id="calendarStream"' in source
    assert "EKONOMİK TAKVİM" in source
    assert "news-title-new" in source
    assert "news-item.new" in source
    assert "state.lastNewsCount" in source
    assert "Sahte haber yok" in source
    assert "Sahte etkinlik yok" in source


def test_public_btc_eth_tickers_have_bounded_fallback_without_secrets():
    source = html()

    assert "BTC/USDT" in source
    assert "ETH/USDT" in source
    assert "api.binance.com/api/v3/ticker/24hr" in source
    assert "api.coingecko.com/api/v3/simple/price" in source
    assert "setInterval(refreshTickers,20000)" in source
    assert "API_KEY" not in source
    assert "PRIVATE_KEY" not in source


def test_panel_preserves_canonical_real_data_and_read_only_contracts():
    source = html()

    assert "getJson('/api/dashboard')" in source
    assert "getJson('/api/runtime-candidates')" in source
    assert "getJson('/api/authority')" in source
    assert "getJson('/api/universe-panel')" in source
    assert "READ ONLY" in source
    assert "LIVE EXECUTION" in source
    assert "WALLET" in source


def test_phase9_wallet_detail_remains_bound_to_real_intelligence_summary():
    source = html()

    assert 'id="walletDetailBody"' in source
    assert "wallet_details_json" in source
    assert "phase9WalletDetails" in source
    assert "phase9Seen" in source
    assert "successful_wallets" in source
    assert "Henüz gerçek Phase 9 wallet detayı yok" in source
    assert "PHASE 9 · READ ONLY" in source


def test_vezir_and_accounting_remain_available():
    source = html()

    assert "VEZİR" in source
    assert "/api/vezir/ask" in source
    assert "MUHASEBE" in source
    assert "openAccounting()" in source
    assert "/api/positions" in source
