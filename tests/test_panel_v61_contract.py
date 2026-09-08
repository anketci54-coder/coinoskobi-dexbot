from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v61_frontend_contract():
    html = (
        ROOT / "app/api/static/index.html"
    ).read_text()

    js = (
        ROOT / "app/api/static/dex-terminal-v61.js"
    ).read_text()

    assert "/static/dex-terminal-v61.js" in html
    assert "/static/dex-terminal-v61.css" in html

    assert "/api/manual-paper/preview-v2" in js
    assert "/api/manual-paper/order-v2" in js
    assert "/api/v61/wallet-readonly" in js
    assert "/api/v61/market-tickers" in js

    assert "MANUEL PAPER AL" in js
    assert "PAPER SATIŞI ONAYLA" in js
    assert "CÜZDAN BAĞLA" in js
    assert "OLUMLU SENARYO" in js
    assert "OLUMSUZ SENARYO" in js
    assert "AIRDROP / IDO / ICO" in js

    assert "PRIVATE_KEY" not in js
    assert "eth_sendRawTransaction" not in js


def test_v61_backend_authority_contract():
    source = (
        ROOT / "app/api/panel_v61.py"
    ).read_text()

    init = (
        ROOT / "app/api/__init__.py"
    ).read_text()

    assert '@app.get("/api/v61/market-tickers")' in source
    assert '@app.get("/api/v61/wallet-readonly")' in source

    assert "fetch_balances_for_address" in source
    assert '"wallet_authority": False' in source
    assert '"signing_authority": False' in source
    assert '"execution_authority": False' in source

    assert "register_panel_v61_routes" in init
