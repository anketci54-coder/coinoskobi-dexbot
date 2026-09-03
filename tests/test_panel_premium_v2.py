from pathlib import Path


CSS = Path("app/api/static/panel-premium-v2.css")
JS = Path("app/api/static/panel-premium-v2.js")
BOOTSTRAP = Path("app/api/__init__.py")


def test_premium_assets_are_loaded_by_canonical_panel_shell():
    source = BOOTSTRAP.read_text(encoding="utf-8")

    assert "/static/panel-premium-v2.css?v=2" in source
    assert "/static/panel-premium-v2.js?v=2" in source
    assert "phase14_premium_responsive_shell" in source
    assert "HTMLResponse" in source


def test_manual_radar_is_position_aware_and_has_active_tab():
    source = JS.read_text(encoding="utf-8")

    assert "function openPositionForRadar" in source
    assert "data-filter=\"ACTIVE\"" in source
    assert "state.filter === 'ACTIVE'" in source
    assert "const side = position ? 'SELL' : 'BUY'" in source
    assert "const label = side === 'BUY' ? 'AL' : 'SAT'" in source
    assert "body.manual-mode .trade-actions" in CSS.read_text(encoding="utf-8")


def test_manual_controls_remain_prepare_only_without_execution_authority():
    source = JS.read_text(encoding="utf-8")

    assert "execution/signing authority kapalı; emir gönderilmedi" in source

    forbidden = (
        "eth_requestAccounts",
        "wallet_switchEthereumChain",
        "eth_sendTransaction",
        "sendTransaction(",
        "signTransaction(",
        "connectWallet(",
    )
    for marker in forbidden:
        assert marker not in source


def test_premium_shell_is_responsive_for_tablet_and_phone():
    source = CSS.read_text(encoding="utf-8")

    assert "@media (max-width:1024px)" in source
    assert "@media (max-width:560px)" in source
    assert 'grid-template-areas:' in source
    assert '"state token token"' in source
    assert "body{overflow:auto}" in source


def test_native_scrollbar_chrome_is_hidden_but_scrolling_remains_available():
    source = CSS.read_text(encoding="utf-8")

    assert ".news-pane" in source
    assert "overflow:auto" in source
    assert "scrollbar-width:none" in source
    assert "::-webkit-scrollbar" in source
    assert "display:none" in source


def test_vezir_live_summary_is_operational_not_equity_echo():
    source = JS.read_text(encoding="utf-8")

    assert "premiumRefreshOperations" in source
    assert "'/api/operations-summary'" in source
    assert "ŞU AN NEDEN İŞLEM YOK?" in source
    assert "radarAgeLabel()" in source
    assert "premiumOpsSignature" in source


def test_news_empty_state_stays_truthful_without_fake_feed():
    source = JS.read_text(encoding="utf-8")

    assert "Gerçek haber sağlayıcısı henüz panel backend’ine bağlı değil" in source
    assert "Gerçek ekonomik takvim kaynağı henüz bağlı değil" in source
    assert "Sahte haber" in source
    assert "Sahte etkinlik" in source
