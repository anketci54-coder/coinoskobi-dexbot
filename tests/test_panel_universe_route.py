import sqlite3

import app.api.panel as panel_module
from app.api import api_universe_panel


def _seed_universe(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE universe_pool_registry(
            chain TEXT,
            dex TEXT,
            pool TEXT,
            token0 TEXT,
            token1 TEXT,
            market_state TEXT,
            latest_liquidity_usd REAL,
            latest_volume_24h REAL,
            latest_price_usd REAL,
            latest_txns_5m INTEGER,
            latest_change_5m REAL,
            latest_snapshot_at TEXT,
            state_changed_at TEXT
        );
        CREATE TABLE universe_seismic_evaluation_v1(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain TEXT,
            dex TEXT,
            pool TEXT,
            observed_at TEXT,
            previous_state TEXT,
            next_state TEXT,
            score REAL,
            price_z REAL,
            volume_z REAL,
            txns_z REAL,
            liquidity_ratio REAL,
            evidence_count INTEGER,
            reason TEXT
        );
        INSERT INTO universe_pool_registry VALUES(
            'bsc','pancakeswap_v2','0xpool','0xt0','0xt1','WARM',
            12000,34000,0.002,9,1.5,
            '2026-08-27T09:00:00Z','2026-08-27T08:59:00Z'
        );
        INSERT INTO universe_seismic_evaluation_v1(
            chain,dex,pool,observed_at,previous_state,next_state,score,
            price_z,volume_z,txns_z,liquidity_ratio,evidence_count,reason
        ) VALUES(
            'bsc','pancakeswap_v2','0xpool','2026-08-27T09:00:00Z',
            'COLD','WARM',6.0,3.1,7.0,5.2,0.91,3,'warm ignition'
        );
        """
    )
    db.commit()
    db.close()


def _universe_route():
    return next(
        route
        for route in panel_module.app.routes
        if getattr(route, 'path', None) == '/api/universe-panel'
    )


def test_universe_panel_route_is_registered_and_read_only(tmp_path, monkeypatch):
    cache_db = tmp_path / 'cache.db'
    _seed_universe(cache_db)
    monkeypatch.setattr(panel_module, 'CACHE_DB', cache_db)

    route = _universe_route()
    assert 'GET' in route.methods
    assert route.endpoint is api_universe_panel

    payload = route.endpoint()
    assert payload['available'] is True
    assert payload['counts']['WARM'] == 1
    assert payload['total_count'] == 1
    assert payload['visible_count'] == 1
    assert payload['transitions']['COLD_TO_WARM'] == 1
    assert payload['rows'][0]['seismic']['score'] == 6.0
    assert payload['rows'][0]['seismic']['reason'] == 'warm ignition'
    assert payload['panel_display_only'] is True
    assert payload['decision_authority'] is False
    assert payload['paper_authority'] is False
    assert payload['live_authority'] is False
    assert payload['wallet_authority'] is False
    assert payload['execution_authority'] is False


def test_universe_panel_route_function_fails_closed_when_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(panel_module, 'CACHE_DB', tmp_path / 'missing.db')
    payload = api_universe_panel()
    assert payload['available'] is False
    assert payload['rows'] == []
    assert payload['execution_authority'] is False
