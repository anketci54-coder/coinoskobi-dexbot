from __future__ import annotations

import sqlite3
from pathlib import Path

from app.universe.display_metadata import TABLE


ALLOWED_QUOTES = {"USDT", "USDC", "WBNB"}


def enrich_universe_display_names(payload, cache_db):
    """Enrich and restrict radar rows to approved quote assets.

    Rows without durable pair metadata are omitted rather than guessing pair
    orientation. Radar quote assets are USDT, USDC and WBNB only.
    """
    if not isinstance(payload, dict) or not payload.get("available"):
        return payload

    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return payload

    pools = list(dict.fromkeys(
        str(row.get("pool") or "").strip().lower()
        for row in rows
        if isinstance(row, dict) and str(row.get("pool") or "").strip()
    ))
    if not pools:
        payload["rows"] = []
        payload["stable_quote_filtered"] = True
        return payload

    connection = None
    try:
        path = Path(cache_db)
        connection = sqlite3.connect(
            f"file:{path}?mode=ro", uri=True, timeout=2,
        )
        connection.row_factory = sqlite3.Row
        marks = ",".join("?" for _ in pools)
        matches = connection.execute(
            f"""
            SELECT pool, display_name, base_symbol, quote_symbol,
                   base_name, quote_name, base_token, quote_token
            FROM {TABLE}
            WHERE lower(pool) IN ({marks})
              AND NULLIF(TRIM(display_name), '') IS NOT NULL
            """,
            tuple(pools),
        ).fetchall()
    except sqlite3.Error:
        return payload
    finally:
        if connection is not None:
            connection.close()

    metadata = {
        str(item["pool"] or "").strip().lower(): dict(item)
        for item in matches
        if str(item["pool"] or "").strip()
    }

    filtered = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        meta = metadata.get(str(row.get("pool") or "").strip().lower())
        if not meta:
            continue
        quote_symbol = str(meta.get("quote_symbol") or "").strip().upper()
        if quote_symbol not in ALLOWED_QUOTES:
            continue

        row["display_name"] = str(meta.get("display_name") or "").strip()
        row["base_symbol"] = str(meta.get("base_symbol") or "").strip() or None
        row["quote_symbol"] = quote_symbol
        row["base_name"] = str(meta.get("base_name") or "").strip() or None
        row["quote_name"] = str(meta.get("quote_name") or "").strip() or None
        row["base_token"] = meta.get("base_token")
        row["quote_token"] = meta.get("quote_token")
        filtered.append(row)

    payload["rows"] = filtered
    payload["display_name_source"] = "UNIVERSE_POOL_DISPLAY_METADATA_V1"
    payload["display_name_matches"] = len(filtered)
    payload["allowed_quote_symbols"] = sorted(ALLOWED_QUOTES)
    payload["stable_quote_filtered"] = True
    return payload


__all__ = ["ALLOWED_QUOTES", "enrich_universe_display_names"]
