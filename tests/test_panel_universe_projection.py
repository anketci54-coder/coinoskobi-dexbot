import sqlite3

from app.api.panel_universe import universe_panel_payload


def _seed(path):
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
        """
    )
    db.executemany(
        """
        INSERT INTO universe_pool_registry VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            ("bsc", "pancakeswap_v2", "0x1", "0xa", "0xb", "HOT", 2000, 9000, 1.2, 14, 4.1, "2026-08-27T08:00:00Z", "2026-08-27T07:59:00Z"),
            ("bsc", "pancakeswap_v3", "0x2", "0xc", "0xd", "WARM", 5000, 7000, 0.8, 7, 1.3, "2026-08-27T07:58:00Z", "2026-08-27T07:57:00Z"),
            ("bsc", "pancakeswap_v2", "0x3", "0xe", "0xf", "COLD", 9000, 3000, 0.4, 1, 0.1, "2026-08-27T07:56:00Z", "2026-08-27T07:55:00Z"),
        ],
    )
    db.executemany(
        """
        INSERT INTO universe_seismic_evaluation_v1(
            chain,dex,pool,observed_at,previous_state,next_state,score,
            price_z,volume_z,txns_z,liquidity_ratio,evidence_count,reason
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            ("bsc", "pancakeswap_v2", "0x1", "2026-08-27T07:59:30Z", "COLD", "WARM", 6.0, 3.1, 7.0, 6.2, 0.95, 3, "warm ignition"),
            ("bsc", "pancakeswap_v2", "0x1", "2026-08-27T08:00:01Z", "WARM", "HOT", 9.0, 5.5, 12.0, 8.1, 0.91, 3, "hot acceleration"),
            ("bsc", "pancakeswap_v3", "0x2", "2026-08-27T07:58:10Z", "COLD", "WARM", 5.0, 3.2, 6.0, 4.2, 0.88, 2, "warm flow"),
            ("bsc", "pancakeswap_v2", "0x3", "2026-08-27T07:56:10Z", "HOT", "COLD", 1.0, -1.2, -0.5, -0.9, 0.76, 1, "cooled"),
        ],
    )
    db.commit()
    db.close()


def test_universe_panel_projection_is_real_and_read_only(tmp_path):
    path = tmp_path / "cache.db"
    _seed(path)

    payload = universe_panel_payload(path)

    assert payload["available"] is True
    assert payload["source"] == "UNIVERSE_CACHE_READ_ONLY"
    assert payload["counts"] == {"COLD": 1, "WARM": 1, "HOT": 1}
    assert payload["total_count"] == 3
    assert payload["visible_count"] == 3
    assert payload["transition_scope"] == "ALL_RECORDED_SEISMIC_EVALUATIONS"
    assert payload["transitions"] == {
        "COLD_TO_WARM": 2,
        "WARM_TO_HOT": 1,
        "HOT_TO_COLD": 1,
    }
    assert [row["state"] for row in payload["rows"]] == ["HOT", "WARM", "COLD"]

    hot = payload["rows"][0]
    assert hot["seismic"]["score"] == 9.0
    assert hot["seismic"]["volume_z"] == 12.0
    assert hot["seismic"]["txns_z"] == 8.1
    assert hot["seismic"]["reason"] == "hot acceleration"
    assert hot["seismic"]["previous_state"] == "WARM"
    assert hot["seismic"]["next_state"] == "HOT"

    assert payload["panel_display_only"] is True
    assert payload["decision_authority"] is False
    assert payload["paper_authority"] is False
    assert payload["live_authority"] is False
    assert payload["wallet_authority"] is False
    assert payload["execution_authority"] is False


def test_universe_panel_projection_fails_closed_when_db_missing(tmp_path):
    payload = universe_panel_payload(tmp_path / "missing.db")

    assert payload["available"] is False
    assert payload["counts"] == {"COLD": None, "WARM": None, "HOT": None}
    assert payload["total_count"] is None
    assert payload["visible_count"] == 0
    assert payload["rows"] == []
    assert payload["execution_authority"] is False
