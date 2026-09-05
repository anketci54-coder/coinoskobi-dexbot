from __future__ import annotations

import json
import math
import sqlite3
import string
import time
from pathlib import Path
from typing import Any, Iterable

from app.paper.wallet_discovery_evidence_schema import (
    MAX_DISCOVERY_CANDIDATES,
    MAX_DISCOVERY_EVIDENCE_ROWS,
    ensure_wallet_discovery_evidence_schema,
)


ALLOWED_SOURCES = {
    "ARKHAM_TOP_TRADERS",
    "ARKHAM_TRADER_TAG",
    "ARKHAM_ADDRESS_TAG_UPDATE",
    "ARKHAM_ADDRESS_UPDATE",
    "TRANSACTION_FROM_ONLY",
}
ALLOWED_CHAINS = {"bsc"}
MAX_SOURCE_KEY_LENGTH = 160
MAX_METADATA_JSON_LENGTH = 4096


def _wallet_parts(chain: Any, address: Any) -> tuple[str, str, str] | None:
    chain_text = str(chain or "").strip().lower()
    address_text = str(address or "").strip().lower()
    if chain_text not in ALLOWED_CHAINS:
        return None
    if len(address_text) != 42 or not address_text.startswith("0x"):
        return None
    if any(ch not in string.hexdigits for ch in address_text[2:]):
        return None
    return f"{chain_text}:{address_text}", chain_text, address_text


def _rank(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _metadata(value: Any) -> str | None:
    if value is None:
        return None
    try:
        encoded = json.dumps(value, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        return None
    return encoded if len(encoded) <= MAX_METADATA_JSON_LENGTH else None


def _ensure_registry(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_discovery_registry(
            wallet_uid TEXT PRIMARY KEY,
            chain TEXT,
            address TEXT,
            first_seen_at REAL,
            last_seen_at REAL,
            discovery_source TEXT,
            freshness_state TEXT,
            lifecycle_state TEXT
        )
        """
    )


def _upsert_registry(
    db: sqlite3.Connection,
    *,
    wallet_uid: str,
    chain: str,
    address: str,
    source: str,
    observed_at: float,
) -> None:
    existing = db.execute(
        "SELECT wallet_uid FROM wallet_discovery_registry WHERE lower(wallet_uid)=lower(?)",
        (wallet_uid,),
    ).fetchone()
    if existing is None:
        db.execute(
            """
            INSERT INTO wallet_discovery_registry(
                wallet_uid,chain,address,first_seen_at,last_seen_at,
                discovery_source,freshness_state,lifecycle_state
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                wallet_uid,
                chain,
                address,
                observed_at,
                observed_at,
                source,
                "FRESH",
                "ACTIVE",
            ),
        )
        return

    db.execute(
        """
        UPDATE wallet_discovery_registry
        SET last_seen_at=?, freshness_state='FRESH', lifecycle_state='ACTIVE'
        WHERE lower(wallet_uid)=lower(?)
        """,
        (observed_at, wallet_uid),
    )


def _prune_candidate_pool(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT lower(wallet_uid) AS wallet_uid, MAX(last_seen_at) AS last_seen_at
        FROM wallet_discovery_source_evidence
        WHERE active=1
        GROUP BY lower(wallet_uid)
        ORDER BY MAX(last_seen_at) DESC, lower(wallet_uid) ASC
        """
    ).fetchall()
    keep = [str(row["wallet_uid"]) for row in rows[:MAX_DISCOVERY_CANDIDATES]]
    if len(rows) <= MAX_DISCOVERY_CANDIDATES:
        return
    placeholders = ",".join("?" for _ in keep)
    db.execute(
        f"""
        UPDATE wallet_discovery_source_evidence
        SET active=0
        WHERE active=1 AND lower(wallet_uid) NOT IN ({placeholders})
        """,
        keep,
    )


def _trim_evidence_rows(db: sqlite3.Connection) -> None:
    db.execute(
        """
        DELETE FROM wallet_discovery_source_evidence
        WHERE rowid NOT IN (
            SELECT rowid
            FROM wallet_discovery_source_evidence
            ORDER BY active DESC, last_seen_at DESC,
                     lower(wallet_uid) ASC, source ASC, source_key ASC
            LIMIT ?
        )
        """,
        (MAX_DISCOVERY_EVIDENCE_ROWS,),
    )


def ingest_wallet_candidates(
    db_path: str | Path,
    candidates: Iterable[dict[str, Any]],
    *,
    source: str,
    source_key: str,
    provider: str = "ARKHAM",
    observed_at: float | None = None,
) -> dict[str, Any]:
    """Ingest BSC wallet candidates without granting success authority."""
    source = str(source or "").strip().upper()
    source_key = str(source_key or "").strip()
    provider = str(provider or "").strip().upper() or "UNKNOWN"
    if source not in ALLOWED_SOURCES:
        raise ValueError("UNSUPPORTED_DISCOVERY_SOURCE")
    if not source_key or len(source_key) > MAX_SOURCE_KEY_LENGTH:
        raise ValueError("INVALID_SOURCE_KEY")

    try:
        seen = float(observed_at if observed_at is not None else time.time())
    except (TypeError, ValueError):
        raise ValueError("INVALID_OBSERVED_AT") from None
    if not math.isfinite(seen) or seen < 0:
        raise ValueError("INVALID_OBSERVED_AT")

    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(path)

    db = sqlite3.connect(str(path), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    accepted = rejected = 0
    try:
        _ensure_registry(db)
        ensure_wallet_discovery_evidence_schema(db)

        for row in candidates:
            if not isinstance(row, dict):
                rejected += 1
                continue
            parts = _wallet_parts(row.get("chain") or "bsc", row.get("address"))
            if parts is None:
                rejected += 1
                continue
            wallet_uid, chain, address = parts
            external_rank = _rank(row.get("external_rank") or row.get("rank"))
            metadata_json = _metadata(row.get("metadata"))

            db.execute(
                """
                INSERT INTO wallet_discovery_source_evidence(
                    wallet_uid,source,source_key,chain,address,candidate_state,
                    external_rank,first_seen_at,last_seen_at,active,metadata_json,provider
                ) VALUES(?,?,?,?,?,'OBSERVED',?,?,?,?,?,?)
                ON CONFLICT(wallet_uid,source,source_key) DO UPDATE SET
                    chain=excluded.chain,
                    address=excluded.address,
                    external_rank=COALESCE(
                        excluded.external_rank,
                        wallet_discovery_source_evidence.external_rank
                    ),
                    last_seen_at=excluded.last_seen_at,
                    active=1,
                    metadata_json=COALESCE(
                        excluded.metadata_json,
                        wallet_discovery_source_evidence.metadata_json
                    ),
                    provider=excluded.provider
                """,
                (
                    wallet_uid,
                    source,
                    source_key,
                    chain,
                    address,
                    external_rank,
                    seen,
                    seen,
                    1,
                    metadata_json,
                    provider,
                ),
            )
            _upsert_registry(
                db,
                wallet_uid=wallet_uid,
                chain=chain,
                address=address,
                source=source,
                observed_at=seen,
            )
            accepted += 1

        _prune_candidate_pool(db)
        _trim_evidence_rows(db)
        db.commit()
        active_candidates = int(
            db.execute(
                "SELECT COUNT(DISTINCT lower(wallet_uid)) FROM wallet_discovery_source_evidence WHERE active=1"
            ).fetchone()[0]
        )
        evidence_rows = int(
            db.execute(
                "SELECT COUNT(*) FROM wallet_discovery_source_evidence"
            ).fetchone()[0]
        )
        return {
            "state": "READY",
            "source": source,
            "source_key": source_key,
            "accepted": accepted,
            "rejected": rejected,
            "active_candidates": active_candidates,
            "evidence_rows": evidence_rows,
            "candidate_cap": MAX_DISCOVERY_CANDIDATES,
            "evidence_row_cap": MAX_DISCOVERY_EVIDENCE_ROWS,
            "candidate_state": "OBSERVED",
            "success_authority": False,
            "trade_authority": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
