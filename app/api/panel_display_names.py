from __future__ import annotations

import sqlite3
from pathlib import Path

from app.universe.display_metadata import TABLE


def enrich_universe_display_names(payload, cache_db):
    """Overlay bounded panel rows with durable provider display metadata.

    Read-only, fail-soft, and identity preserving. The payload's token/pool
    addresses are never replaced.
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
        return payload

    connection = None
    try:
        path = Path(cache_db)
        connection = sqlite3.connect(
            f"file:{path}?mode=ro",
            uri=True,
            timeout=2,
        )
        connection.row_factory = sqlite3.Row
        marks = ",".join("?" for _ in pools)
        matches = connection.execute(
            f"""
            SELECT pool, display_name
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

    names = {
        str(row["pool"] or "").strip().lower(): str(
            row["display_name"] or ""
        ).strip()
        for row in matches
        if str(row["pool"] or "").strip() and str(row["display_name"] or "").strip()
    }

    for row in rows:
        if not isinstance(row, dict):
            continue
        name = names.get(str(row.get("pool") or "").strip().lower())
        if name:
            row["display_name"] = name

    payload["display_name_source"] = "UNIVERSE_POOL_DISPLAY_METADATA_V1"
    payload["display_name_matches"] = sum(
        1 for row in rows if isinstance(row, dict) and row.get("display_name")
    )
    return payload


__all__ = ["enrich_universe_display_names"]
