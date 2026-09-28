import sqlite3

from app.api.panel_display_names import enrich_universe_display_names
from app.universe.display_metadata import TABLE


def test_filtered_counts_match_visible_usdt_rows(tmp_path):
    db = tmp_path / "cache.db"
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
        f"INSERT INTO {TABLE} VALUES (?,?,?,?,?,?,?,?)",
        [
            ("0xhot", "HOTX / WBNB", "HOTX", "WBNB", "", "", "", ""),
            ("0xwarm", "WARMX / USDT", "WARMX", "USDT", "", "", "", ""),
        ],
    )
    con.commit()
    con.close()

    payload = {
        "available": True,
        "counts": {"HOT": 99, "WARM": 77, "COLD": 55},
        "visible_count": 231,
        "rows": [
            {
                "pool": "0xhot",
                "state": "HOT",
                "chain": "bsc",
                "dex": "pancakeswap_v2",
            },
            {
                "pool": "0xwarm",
                "state": "WARM",
                "chain": "bsc",
                "dex": "pancakeswap_v2",
            },
        ],
    }

    result = enrich_universe_display_names(payload, db)

    assert result["counts"] == {"HOT": 0, "WARM": 1, "COLD": 0}
    assert result["visible_count"] == 1
    assert result["total_count"] == 1
    assert result["rows"][0]["display_name"] == "WARMX / USDT"
