import sqlite3

from app.api.panel_display_names import enrich_universe_display_names
from app.universe.display_metadata import persist_snapshot_display_metadata


def test_persist_snapshot_display_metadata_and_overlay_panel(tmp_path):
    path = tmp_path / "cache.db"
    db = sqlite3.connect(path)

    written = persist_snapshot_display_metadata(
        db,
        [
            {
                "chain": "bsc",
                "dex": "pancakeswap_v2",
                "pool": "0x0000000000000000000000000000000000000001",
                "base_token": "0x0000000000000000000000000000000000000002",
                "quote_token": "0x0000000000000000000000000000000000000003",
                "base_symbol": "ALPHA",
                "quote_symbol": "WBNB",
                "base_name": "Alpha Token",
                "quote_name": "Wrapped BNB",
                "display_name": "ALPHA / WBNB",
                "source": "dexscreener",
                "observed_at": "2026-08-28T12:00:00+00:00",
            }
        ],
    )
    db.close()

    assert written == 1

    payload = {
        "available": True,
        "rows": [
            {
                "pool": "0x0000000000000000000000000000000000000001",
                "token0": "0x0000000000000000000000000000000000000002",
                "display_name": None,
            }
        ],
    }

    result = enrich_universe_display_names(payload, path)

    assert result["rows"][0]["display_name"] == "ALPHA / WBNB"
    assert result["rows"][0]["token0"].endswith("0002")
    assert result["display_name_matches"] == 1
    assert result["display_name_source"] == "UNIVERSE_POOL_DISPLAY_METADATA_V1"


def test_panel_overlay_missing_metadata_table_is_fail_soft(tmp_path):
    path = tmp_path / "cache.db"
    sqlite3.connect(path).close()

    payload = {
        "available": True,
        "rows": [
            {
                "pool": "0x0000000000000000000000000000000000000001",
                "token0": "0x0000000000000000000000000000000000000002",
                "display_name": None,
            }
        ],
    }

    result = enrich_universe_display_names(payload, path)

    assert result is payload
    assert result["rows"][0]["display_name"] is None
