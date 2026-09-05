from __future__ import annotations


WALLET_DISCOVERY_EVIDENCE_SCHEMA_VERSION = 1
MAX_DISCOVERY_CANDIDATES = 5000

REQUIRED_TABLES = (
    "wallet_discovery_source_evidence",
)


def ensure_wallet_discovery_evidence_schema(conn) -> dict[str, object]:
    """Install bounded, observation-only multi-source wallet discovery evidence."""
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS wallet_discovery_source_evidence(
                wallet_uid TEXT NOT NULL,
                source TEXT NOT NULL,
                source_key TEXT NOT NULL,
                chain TEXT NOT NULL,
                address TEXT NOT NULL,
                candidate_state TEXT NOT NULL DEFAULT 'OBSERVED',
                external_rank INTEGER,
                first_seen_at REAL NOT NULL,
                last_seen_at REAL NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                metadata_json TEXT,
                provider TEXT,
                PRIMARY KEY(wallet_uid, source, source_key)
            );
            CREATE INDEX IF NOT EXISTS idx_wallet_discovery_evidence_recent
            ON wallet_discovery_source_evidence(active, last_seen_at DESC);
            CREATE INDEX IF NOT EXISTS idx_wallet_discovery_evidence_source
            ON wallet_discovery_source_evidence(source, active, external_rank, last_seen_at DESC);
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    existing = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing = [name for name in REQUIRED_TABLES if name not in existing]
    if missing:
        raise RuntimeError(
            "wallet discovery evidence schema missing tables: " + ", ".join(missing)
        )

    return {
        "state": "READY",
        "schema_version": WALLET_DISCOVERY_EVIDENCE_SCHEMA_VERSION,
        "candidate_cap": MAX_DISCOVERY_CANDIDATES,
        "tables": list(REQUIRED_TABLES),
        "read_only_evidence": True,
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
