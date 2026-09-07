from pathlib import Path
import sqlite3

import pytest

from app.api import panel_portfolio_marks_v2 as marks


def _paper_db(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE paper_trades(
            id INTEGER PRIMARY KEY,
            token TEXT,
            symbol TEXT,
            pool TEXT,
            entry_price REAL,
            current_price REAL,
            token_amount REAL,
            entry_amount_usdt REAL,
            realized_gross_proceeds_usdt REAL DEFAULT 0,
            realized_proceeds_usdt REAL DEFAULT 0,
            mathematical_plan_json TEXT,
            paper_account_version TEXT,
            trade_policy TEXT,
            status TEXT,
            net_pnl_usdt REAL,
            net_pnl REAL
        );
        INSERT INTO paper_trades(
            id, token, symbol, pool, entry_price, current_price,
            token_amount, entry_amount_usdt, paper_account_version,
            trade_policy, status
        ) VALUES(
            1, '0xtoken', 'TEST', '0xpool', 1.0, 1.0,
            100.0, 100.0, 'PAPER_10K_V2', 'MANUAL_PANEL', 'OPEN'
        );
        INSERT INTO paper_trades(
            id, token, symbol, pool, entry_price, current_price,
            token_amount, entry_amount_usdt, paper_account_version,
            trade_policy, status, net_pnl_usdt
        ) VALUES(
            2, '0xclosed', 'OLD', '0xclosedpool', 1.0, 0.9,
            0.0, 100.0, 'PAPER_10K_V2', 'MANUAL_PANEL', 'CLOSED', -10.0
        );
        """
    )
    db.commit()
    db.close()


def _cache_db(path: Path, *, updated_at: str) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE universe_pool_registry(
            pool TEXT,
            latest_price_usd REAL,
            latest_snapshot_at TEXT,
            dex TEXT
        );
        CREATE TABLE gecko_pool_cache(
            pool TEXT,
            price_usd REAL,
            updated_at TEXT,
            dex TEXT
        );
        """
    )
    db.execute(
        "INSERT INTO universe_pool_registry VALUES(?,?,?,?)",
        ('0xpool', 1.10, updated_at, 'pancake'),
    )
    db.commit()
    db.close()


def test_live_provider_mark_reprices_manual_open_position(tmp_path, monkeypatch):
    paper = tmp_path / 'paper.db'
    cache = tmp_path / 'cache.db'
    _paper_db(paper)
    _cache_db(cache, updated_at='2000-01-01T00:00:00+00:00')

    monkeypatch.setattr(
        marks,
        '_provider_quotes',
        lambda pools: ({
            '0xpool': {
                'pool': '0xpool',
                'price_usd': 1.20,
                'observed_at': marks.time.time(),
                'updated_at': 'now',
                'dex': 'pancake',
                'source': 'GECKOTERMINAL_MULTI_POOL',
            }
        }, 'OK'),
    )

    payload = marks._build_payload(
        marks._open_positions(paper),
        paper_db=paper,
        cache_db=cache,
    )

    row = payload['rows'][0]
    assert row['db_current_price'] == pytest.approx(1.0)
    assert row['mark_price_usd'] == pytest.approx(1.2)
    assert row['mark_price_fresh'] is True
    assert row['mark_value_usdt'] == pytest.approx(120.0)
    assert row['estimated_exit_net_pnl_usdt'] == pytest.approx(20.0)
    assert row['estimated_exit_roi_pct'] == pytest.approx(20.0)
    assert payload['summary']['fresh_mark_count'] == 1
    assert payload['summary']['open_mark_net_pnl_usdt'] == pytest.approx(20.0)
    assert payload['summary']['realized_net_usdt'] == pytest.approx(-10.0)
    assert payload['summary']['mark_equity_usdt'] == pytest.approx(10010.0)


def test_stale_external_price_fails_closed_to_paper_db(tmp_path, monkeypatch):
    paper = tmp_path / 'paper.db'
    cache = tmp_path / 'cache.db'
    _paper_db(paper)
    _cache_db(cache, updated_at='2000-01-01T00:00:00+00:00')

    monkeypatch.setattr(marks, '_provider_quotes', lambda pools: ({}, 'HTTPError'))

    payload = marks._build_payload(
        marks._open_positions(paper),
        paper_db=paper,
        cache_db=cache,
    )

    row = payload['rows'][0]
    assert row['mark_price_usd'] == pytest.approx(1.0)
    assert row['mark_price_fresh'] is False
    assert row['mark_price_source'] == 'PAPER_DB_FALLBACK_STALE_EXTERNAL'
    assert payload['summary']['fresh_mark_count'] == 0
    assert payload['summary']['open_mark_net_pnl_usdt'] is None
    assert payload['summary']['mark_equity_usdt'] is None


def test_readmodel_has_no_write_or_execution_authority():
    source = Path(marks.__file__).read_text(encoding='utf-8')

    assert '@app.get("/api/portfolio-marks-v2")' in source
    assert 'persist_followups=False' in source
    assert 'mode=ro' in source

    for forbidden in (
        'INSERT INTO paper_trades',
        'UPDATE paper_trades',
        'DELETE FROM paper_trades',
        'eth_sendRawTransaction',
        'PRIVATE_KEY',
        'WALLET_ADDRESS',
    ):
        assert forbidden not in source


def test_premium_accounting_consumes_live_marks():
    js = (
        Path(__file__).resolve().parents[1]
        / 'app' / 'api' / 'static' / 'panel-premium-accounting-v5.js'
    ).read_text(encoding='utf-8')

    assert "get('/api/portfolio-marks-v2')" in js
    assert 'mark_price_usd' in js
    assert 'estimated_exit_net_pnl_usdt' in js
    assert 'TAHMİNİ ÇIKIŞ PNL' in js
    assert 'TAZE MARK YOK' in js
