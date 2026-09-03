from pathlib import Path


PANEL = Path("app/api/static/index.html")


def html() -> str:
    return PANEL.read_text(encoding="utf-8")


def test_header_keeps_brand_and_real_paper_metrics():
    source = html()
    assert "grid-template-rows:92px minmax(0,1fr) 34px" in source
    assert "İŞLEM<br>MERKEZİ" in source
    for marker in ("BAKİYE", "GÜNLÜK PNL", "TOPLAM PNL", "AÇIK POZİSYON", "KULLANILAN RİSK"):
        assert marker in source


def test_radar_is_single_canonical_center_without_bottom_state_bar():
    source = html()
    assert "RADAR MERKEZİ" in source
    assert "UNIVERSE RADAR" not in source
    assert "FIRSAT RADARI" not in source
    assert 'class="distribution"' not in source
    assert 'id="universeSource"' not in source


def test_radar_has_requested_columns_filters_and_active_positions_tab():
    source = html()
    header = (
        '<div class="radar-grid"><span>STATE</span>'
        '<span>VARLIK / POOL</span><span>SCORE</span>'
        '<span>24H HACİM</span><span>FİYAT</span>'
        '<span>5M</span><span>LİKİDİTE</span></div>'
    )
    assert header in source
    assert "n(r.seismic.score)>0" in source
    assert ".sort((a,b)=>n(b?.seismic?.score)-n(a?.seismic?.score))" in source
    for marker in ('data-filter="ALL"', 'data-filter="COLD"', 'data-filter="WARM"', 'data-filter="HOT"', 'data-filter="ACTIVE"'):
        assert marker in source
    assert "openPositionForRadar" in source


def test_radar_uses_readable_pair_name_and_hover_detail():
    source = html()
    assert "r.display_name" in source
    assert 'class="token-tooltip"' in source
    assert "snapshot_at" in source
    assert "liquidity_usd" in source


def test_manual_buy_sell_is_real_paper_only_with_confirmed_order_ticket():
    source = html()
    assert '>AL</button>' in source
    assert '>SAT</button>' in source
    assert "state.operatingMode!=='MANUAL'" in source
    assert "openOrderTicket" in source
    assert "'/api/manual-paper/order'" in source
    assert "confirmed:true" in source
    assert "ALIM MİKTARI (USDT)" in source
    assert "ALIMI ONAYLA" in source
    assert "SATIŞI ONAYLA" in source
    assert "Sadece PAPER hesap" in source
    for marker in ("eth_requestAccounts", "wallet_switchEthereumChain", "eth_sendTransaction", "sendTransaction(", "connectWallet(", "signTransaction(", "PRIVATE_KEY"):
        assert marker not in source


def test_news_and_calendar_are_immediately_below_radar():
    source = html()
    radar_end = source.index('</section>\n\n<section class="panel news">')
    news_start = source.index('<section class="panel news">')
    lower_start = source.index('<div class="middle">')
    assert radar_end < news_start < lower_start
    assert 'id="newsTitle">HABER AKIŞI (0)' in source
    assert 'id="newsStream"' in source
    assert 'id="calendarStream"' in source
    assert "EKONOMİK TAKVİM" in source
    assert "Sahte haber yok" in source
    assert "Sahte etkinlik yok" in source


def test_wallet_panel_has_no_internal_phase_label_but_keeps_real_binding():
    source = html()
    assert "PHASE 9" not in source
    assert 'id="walletDetailBody"' in source
    assert "wallet_details_json" in source
    assert "successful_wallets" in source
    assert "Henüz gerçek wallet detayı yok" in source


def test_vezir_is_single_chat_path_and_reports_provider_system_state():
    source = html()
    assert "VEZİR" in source
    assert "/api/vezir/ask" in source
    assert "/api/operations-summary" in source
    assert "sendVezir" in source
    assert "provider" in source.lower()
    assert "SADECE OKUMA" in source


def test_public_tickers_and_canonical_real_data_routes_remain():
    source = html()
    assert "api.binance.com/api/v3/ticker/24hr" in source
    assert "api.coingecko.com/api/v3/simple/price" in source
    assert "setInterval(refreshTickers,20000)" in source
    for marker in ("getJson('/api/dashboard')", "getJson('/api/runtime-candidates')", "getJson('/api/authority')", "getJson('/api/universe-panel')"):
        assert marker in source
    assert "LIVE EXECUTION" in source
    assert "WALLET" in source


def test_accounting_remains_available():
    source = html()
    assert "MUHASEBE" in source
    assert "openAccounting()" in source
    assert "/api/positions" in source
