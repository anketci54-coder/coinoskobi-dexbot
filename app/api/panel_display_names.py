from __future__ import annotations

import sqlite3
from pathlib import Path

from app.universe.display_metadata import TABLE


ALLOWED_QUOTES = {"USDT"}


def enrich_universe_display_names(payload, cache_db):
    """Enrich radar rows without narrowing the discovery universe.

    Durable metadata is used when available. PAPER quote eligibility remains
    USDT-only and is exposed as a row flag; it does not hide HOT/WARM rows
    from the read-only radar.
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
        payload["stable_quote_filtered"] = False
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

    enriched = []
    metadata_matches = 0

    for row in rows:
        if not isinstance(row, dict):
            continue

        pool = str(
            row.get("pool") or ""
        ).strip().lower()
        meta = metadata.get(pool)

        if not meta:
            continue

        quote_symbol = str(
            meta.get("quote_symbol") or ""
        ).strip().upper()
        base_symbol = str(
            meta.get("base_symbol") or ""
        ).strip().upper()
        chain = str(
            row.get("chain") or ""
        ).strip().lower()
        dex = str(
            row.get("dex") or ""
        ).strip().lower()

        if chain != "bsc":
            continue
        if dex not in {
            "pancakeswap_v2",
            "pancakeswap_v3",
        }:
            continue
        if quote_symbol != "USDT":
            continue
        if base_symbol in {
            "",
            "USDT",
            "WBNB",
        }:
            continue

        row["display_name"] = str(
            meta.get("display_name") or ""
        ).strip() or row.get("display_name")
        row["base_symbol"] = base_symbol
        row["quote_symbol"] = quote_symbol
        row["base_name"] = str(
            meta.get("base_name") or ""
        ).strip() or None
        row["quote_name"] = str(
            meta.get("quote_name") or ""
        ).strip() or None
        row["base_token"] = (
            meta.get("base_token")
            or row.get("base_token")
        )
        row["quote_token"] = (
            meta.get("quote_token")
            or row.get("quote_token")
        )
        row["paper_quote_eligible"] = True
        metadata_matches += 1
        enriched.append(row)

    payload["rows"] = enriched

    filtered_counts = {
        "COLD": 0,
        "WARM": 0,
        "HOT": 0,
    }
    for row in enriched:
        state = str(
            row.get("state") or ""
        ).upper()
        if state in filtered_counts:
            filtered_counts[state] += 1

    payload["counts"] = filtered_counts
    payload["total_count"] = sum(
        filtered_counts.values()
    )
    payload["visible_count"] = len(enriched)
    payload["display_name_source"] = "UNIVERSE_POOL_DISPLAY_METADATA_V1"
    payload["display_name_matches"] = metadata_matches
    payload["allowed_quote_symbols"] = sorted(ALLOWED_QUOTES)
    payload["stable_quote_filtered"] = True
    return payload


__all__ = ["ALLOWED_QUOTES", "enrich_universe_display_names"]
