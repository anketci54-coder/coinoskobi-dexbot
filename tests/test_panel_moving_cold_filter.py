import sqlite3

from app.api.panel_display_names import enrich_universe_display_names
from app.universe.display_metadata import TABLE


def _db(path):
    con = sqlite3.connect(path)
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
        f"INSERT INTO {TABLE} VALUES (?,?,?,?,?,?,?,?)",
        [
            ("0xdead", "DEAD / USDT", "DEAD", "USDT", "", "", "", ""),
            ("0xprice", "PRICE / USDT", "PRICE", "USDT", "", "", "", ""),
            ("0xtxn", "TXN / USDT", "TXN", "USDT", "", "", "", ""),
        ],
    )
    con.commit()
    con.close()


def test_cold_requires_current_5m_movement(tmp_path):
    db = tmp_path / "cache.db"
    _db(db)

    payload = {
        "available": True,
        "rows": [
            {
                "pool": "0xdead",
                "state": "COLD",
                "chain": "bsc",
                "dex": "pancakeswap_v2",
                "change_5m_pct": 0.0,
                "txns_5m": 0,
            },
            {
                "pool": "0xprice",
                "state": "COLD",
                "chain": "bsc",
                "dex": "pancakeswap_v2",
                "change_5m_pct": 0.001,
                "txns_5m": 0,
            },
            {
                "pool": "0xtxn",
                "state": "COLD",
                "chain": "bsc",
                "dex": "pancakeswap_v2",
                "change_5m_pct": 0.0,
                "txns_5m": 1,
            },
        ],
    }

    result = enrich_universe_display_names(payload, db)

    names = [row["display_name"] for row in result["rows"]]
    assert "DEAD / USDT" not in names
    assert "PRICE / USDT" in names
    assert "TXN / USDT" in names
    assert result["counts"]["COLD"] == 2
