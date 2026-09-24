import sqlite3

from app.api.panel_universe import universe_panel_payload


def _seed(path, *, with_gecko):
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
            'bsc','pancakeswap_v2','0xpool','0xtoken','0xquote','HOT',
            12000,34000,0.002,9,1.5,
            '2026-08-28T09:00:00Z','2026-08-28T08:59:00Z'
        );
        """
    )
    if with_gecko:
        db.executescript(
            """
            CREATE TABLE gecko_pool_cache(
                pool TEXT PRIMARY KEY,
                name TEXT
            );
            INSERT INTO gecko_pool_cache VALUES(
                '0xpool','ALPHA / WBNB'
            );
            """
        )
    db.commit()
    db.close()


def test_universe_payload_adds_bounded_gecko_display_name(tmp_path):
    path = tmp_path / 'cache.db'
    _seed(path, with_gecko=True)

    payload = universe_panel_payload(path)

    assert payload['available'] is True
    assert payload['visible_count'] == 1
    assert payload['rows'][0]['display_name'] == 'ALPHA / WBNB'
    assert payload['rows'][0]['token0'] == '0xtoken'
    assert payload['decision_authority'] is False
    assert payload['execution_authority'] is False


def test_universe_payload_missing_gecko_table_is_fail_soft(tmp_path):
    path = tmp_path / 'cache.db'
    _seed(path, with_gecko=False)

    payload = universe_panel_payload(path)

    assert payload['available'] is True
    assert payload['visible_count'] == 1
    assert payload['rows'][0]['display_name'] is None
    assert payload['rows'][0]['token0'] == '0xtoken'


def test_panel_display_names_excludes_wbnb_as_base_but_keeps_wbnb_as_quote(tmp_path):
    import sqlite3

    from app.api.panel_display_names import enrich_universe_display_names
    from app.universe.display_metadata import TABLE

    db = tmp_path / "panel_wbnb_filter.sqlite3"
    con = sqlite3.connect(db)

    con.execute(
        f"""
        CREATE TABLE {TABLE} (
            pool TEXT PRIMARY KEY,
            display_name TEXT,
            base_symbol TEXT,
            quote_symbol TEXT,
            base_name TEXT,
            quote_name TEXT,
            base_token TEXT,
            quote_token TEXT
        )
        """
    )

    con.executemany(
        f"""
        INSERT INTO {TABLE} (
            pool,
            display_name,
            base_symbol,
            quote_symbol,
            base_name,
            quote_name,
            base_token,
            quote_token
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "0xpool_wbnb_base",
                "WBNB / USDT",
                "WBNB",
                "USDT",
                "Wrapped BNB",
                "Tether USD",
                "0xwbnb",
                "0xusdt",
            ),
            (
                "0xpool_token_wbnb",
                "TEST / WBNB",
                "TEST",
                "WBNB",
                "Test Token",
                "Wrapped BNB",
                "0xtest",
                "0xwbnb",
            ),
        ],
    )
    con.commit()
    con.close()

    payload = {
        "available": True,
        "rows": [
            {"pool": "0xpool_wbnb_base"},
            {"pool": "0xpool_token_wbnb"},
        ],
    }

    result = enrich_universe_display_names(payload, db)

    assert len(result["rows"]) == 1
    assert result["rows"][0]["pool"] == "0xpool_token_wbnb"
    assert result["rows"][0]["base_symbol"] == "TEST"
    assert result["rows"][0]["quote_symbol"] == "WBNB"
