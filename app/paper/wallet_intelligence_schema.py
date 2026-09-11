from __future__ import annotations


WALLET_INTELLIGENCE_SCHEMA_VERSION = 1

REQUIRED_TABLES = (
    "wallet_discovery_registry",
    "wallet_success_score",
    "wallet_outcome_evidence",
    "whale_activity_snapshot",
)


def ensure_wallet_intelligence_schema(conn) -> dict[str, object]:
    """Install Phase 9 wallet observation/read-model persistence.

    The tables live in the canonical paper database but carry observation and
    learning evidence only. They grant no decision, paper, live, wallet,
    signing, or execution authority.
    """
    try:
        conn.executescript(
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
            );

            CREATE TABLE IF NOT EXISTS wallet_success_score(
                wallet_uid TEXT PRIMARY KEY,
                calculated_at REAL,
                sample_depth INTEGER,
                consistency_score REAL,
                entry_quality_score REAL,
                exit_quality_score REAL,
                loss_control_score REAL,
                risk_adjusted_score REAL,
                freshness_score REAL,
                success_score REAL,
                qualification_state TEXT
            );

            CREATE TABLE IF NOT EXISTS wallet_outcome_evidence(
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_uid TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                token_key TEXT,
                evidence_type TEXT NOT NULL,
                outcome_value REAL,
                evidence_quality REAL NOT NULL,
                provenance TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_wallet_outcome_evidence_wallet
            ON wallet_outcome_evidence(
                wallet_uid,
                evidence_type,
                evidence_id DESC
            );

            CREATE TABLE IF NOT EXISTS whale_activity_snapshot(
                wallet_uid TEXT PRIMARY KEY,
                generated_at REAL,
                whale_state TEXT,
                direction TEXT,
                activity_score REAL,
                evidence_count INTEGER
            );
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
    missing = [
        name
        for name in REQUIRED_TABLES
        if name not in existing
    ]
    if missing:
        raise RuntimeError(
            "wallet intelligence schema missing tables: "
            + ", ".join(missing)
        )

    return {
        "state": "READY",
        "schema_version": WALLET_INTELLIGENCE_SCHEMA_VERSION,
        "tables": list(REQUIRED_TABLES),
        "observation_only": True,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
