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
    rows = []
    for i in range(3):
        rows.append((
            "bsc","pancakeswap_v2",f"0xh{i}",
            "0xa","0xb","HOT",10000,5000,1,10,
            float(10-i),"2026-09-28T08:00:00Z","2026-09-28T07:59:00Z"
        ))
    for i in range(45):
        rows.append((
            "bsc","pancakeswap_v2",f"0xw{i}",
            "0xa","0xb","WARM",10000,5000,1,10,
            float(100-i),"2026-09-28T08:00:00Z","2026-09-28T07:59:00Z"
        ))
    db.executemany(
        "INSERT INTO universe_pool_registry VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    db.commit()
    db.close()


def test_all_hot_warm_are_visible_and_sorted_by_5m_change(tmp_path):
    path = tmp_path / "cache.db"
    _seed(path)

    payload = universe_panel_payload(path, limit=2)
    active = [
        row for row in payload["rows"]
        if row["state"] in {"HOT", "WARM"}
    ]

    assert len(active) == 48
    assert {row["state"] for row in active} == {"HOT", "WARM"}
    changes = [row["change_5m_pct"] for row in active]
    assert changes == sorted(changes, reverse=True)
    assert active[0]["change_5m_pct"] == 100.0
