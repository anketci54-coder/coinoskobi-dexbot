from pathlib import Path


HTML = Path("app/api/static/index.html")
JS = Path("app/api/static/panel.js")
CSS = Path("app/api/static/panel.css")


def html() -> str:
    return HTML.read_text(encoding="utf-8")


def js() -> str:
    return JS.read_text(encoding="utf-8")


def css() -> str:
    return CSS.read_text(encoding="utf-8")


def test_single_canonical_asset_runtime():
    source = html()
    assert source.count('<script src="/static/panel.js?v=1"></script>') == 1
    assert source.count('<link rel="stylesheet" href="/static/panel.css?v=1">') == 1
    assert "<style>" not in source
    assert "setInterval(" not in source
    for obsolete in ("panel-premium-v2", "panel-radar-trade-v3", "panel-readable.css"):
        assert obsolete not in source


def test_header_keeps_brand_and_real_paper_metrics():
    source = html()
    assert "grid-template-rows:92px minmax(0,1fr) 34px" in css()
    assert "İŞLEM<br>MERKEZİ" in source
    for marker in ("BAKİYE", "GÜNLÜK PNL", "TOPLAM PNL", "AÇIK POZİSYON", "KULLANILAN RİSK"):
        assert marker in source


def test_radar_is_single_canonical_center_without_legacy_distribution():
    source = html()
    assert "RADAR MERKEZİ" in source
    assert "UNIVERSE RADAR" not in source
    assert "FIRSAT RADARI" not in source
    assert 'class="distribution"' not in source
    assert 'id="universeSource"' not in source


def test_radar_has_requested_columns_filters_and_active_positions_tab():
    markup, runtime = html(), js()
    header = ('<div class="radar-grid"><span>STATE</span><span>VARLIK / POOL</span>'
              '<span>SCORE</span><span>24H HACİM</span><span>FİYAT</span>'
              '<span>5M</span><span>LİKİDİTE</span></div>')
    assert header in markup
    assert "n(r.seismic.score)>0" in runtime
    assert ".sort((a,b)=>n(b?.seismic?.score)-n(a?.seismic?.score))" in runtime
    for marker in ('data-filter="ALL"', 'data-filter="COLD"', 'data-filter="WARM"', 'data-filter="HOT"', 'data-filter="ACTIVE"'):
        assert marker in markup
    assert "openPositionForRadar" in runtime
    assert "activePositionRows" in runtime
    assert "open.map(p=>source.find" in runtime
    assert "state.filter!=='ACTIVE'&&!state.universe?.available" in runtime


def test_radar_uses_readable_pair_name_and_hover_detail():
    runtime = js()
    assert "row?.display_name" in runtime
    assert 'class="token-tooltip"' in runtime
    assert "snapshot_at" in runtime
    assert "liquidity_usd" in runtime


def test_manual_buy_sell_is_real_paper_only_with_confirmed_order_ticket():
    runtime = js()
    assert "side=pos?'SELL':'BUY'" in runtime
    assert "action=pos?'SAT':'AL'" in runtime
    assert "state.operatingMode!=='MANUAL'" in runtime
    assert "openOrderTicket" in runtime
    assert "'/api/manual-paper/order'" in runtime
    assert "confirmed:true" in runtime
    assert "ALIM MİKTARI (USDT)" in runtime
    assert "ALIMI ONAYLA" in runtime
    assert "SATIŞI ONAYLA" in runtime
    assert "Sadece PAPER hesap" in runtime
    for marker in ("eth_requestAccounts", "wallet_switchEthereumChain", "eth_sendTransaction", "sendTransaction(", "connectWallet(", "signTransaction(", "PRIVATE_KEY"):
        assert marker not in runtime


def test_news_and_calendar_are_immediately_below_radar():
    source = html()
    radar_end = source.index('</section>\n\n<section class="panel news">')
    news_start = source.index('<section class="panel news">')
    lower_start = source.index('<div class="middle">')
    assert radar_end < news_start < lower_start
    for marker in ('id="newsTitle">HABER AKIŞI (0)', 'id="newsStream"', 'id="calendarStream"', "EKONOMİK TAKVİM", "Sahte haber yok", "Sahte etkinlik yok"):
        assert marker in source


def test_wallet_panel_has_no_internal_phase_label_but_keeps_real_binding():
    markup, runtime = html(), js()
    assert "PHASE 9" not in markup
    assert 'id="walletDetailBody"' in markup
    assert "wallet_details_json" in runtime
    assert "successful_wallets" in runtime
    assert "Henüz gerçek wallet detayı yok" in runtime


def test_vezir_is_single_chat_path_and_reports_provider_system_state():
    markup, runtime = html(), js()
    assert "VEZİR" in markup
    assert "OPERASYON ASİSTANI" in markup
    assert runtime.count("/api/vezir/ask") == 1
    assert "/api/operations-summary" in runtime
    assert "sendVezir" in runtime
    assert "provider" in runtime.lower()


def test_refresh_never_marks_partial_or_failed_snapshot_fresh():
    runtime = js()
    assert "allFresh=results.every(r=>r.status==='fulfilled')" in runtime
    assert "allFresh?new Date().toLocaleTimeString('tr-TR'):'VERİ HATASI'" in runtime


def test_public_tickers_and_canonical_real_data_routes_remain():
    markup, runtime = html(), js()
    assert "api.binance.com/api/v3/ticker/24hr" in runtime
    assert "api.coingecko.com/api/v3/simple/price" in runtime
    assert "setInterval(refreshTickers,20000)" in runtime
    for marker in ("getJson('/api/dashboard')", "getJson('/api/authority')", "getJson('/api/universe-panel')"):
        assert marker in runtime
    assert "/api/runtime-candidates" not in runtime
    assert "LIVE EXECUTION" in markup
    assert "WALLET" in markup


def test_accounting_remains_available():
    markup, runtime = html(), js()
    assert "MUHASEBE" in markup
    assert "openAccounting()" in markup
    assert "/api/positions" in runtime
