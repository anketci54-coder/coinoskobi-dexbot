import json
import sqlite3

from app.learning.runtime_outcome_feed import (
    RuntimeLearningOutcomeFeed,
)


WALLET = (
    "bsc:"
    "0x1111111111111111111111111111111111111111"
)


def make_db(path):
    db = sqlite3.connect(path)

    db.executescript(
        """
        CREATE TABLE wallet_discovery_registry(
            wallet_uid TEXT PRIMARY KEY,
            chain TEXT,
            address TEXT,
            first_seen_at REAL,
            last_seen_at REAL,
            discovery_source TEXT,
            freshness_state TEXT,
            lifecycle_state TEXT
        );

        CREATE TABLE wallet_outcome_evidence(
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_uid TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            token_key TEXT,
            evidence_type TEXT NOT NULL,
            outcome_value REAL,
            evidence_quality REAL NOT NULL,
            provenance TEXT NOT NULL
        );

        CREATE TABLE paper_trades(
            id INTEGER PRIMARY KEY,
            token TEXT,
            closed_at TEXT,
            roi REAL,
            opening_context_json TEXT,
            status TEXT
        );
        """
    )

    db.execute(
        """
        INSERT INTO wallet_discovery_registry(
            wallet_uid,
            chain,
            address,
            discovery_source,
            freshness_state,
            lifecycle_state
        )
        VALUES(?, 'bsc', ?, 'TRANSACTION_FROM_ONLY',
               'FRESH', 'ACTIVE')
        """,
        (
            WALLET,
            WALLET.split(":", 1)[1],
        ),
    )

    db.commit()
    db.close()


def eligible_context():
    return {
        "actor_identity": {
            "wallet_id": WALLET,
            "identity_source":
                "TRANSACTION_FROM_ONLY",
            "hindsight_reconstructed": False,
        }
    }


def test_historical_backfill_and_hydration(tmp_path):
    path = tmp_path / "paper.db"
    make_db(path)

    db = sqlite3.connect(path)

    db.execute(
        """
        INSERT INTO paper_trades(
            id,
            token,
            closed_at,
            roi,
            opening_context_json,
            status
        )
        VALUES(1, '0xtoken', ?, 0.125, ?, 'CLOSED')
        """,
        (
            "2026-09-08T12:00:00+00:00",
            json.dumps(
                eligible_context()
            ),
        ),
    )

    db.commit()
    db.close()

    calls = []

    def observer(
        wallet_id,
        token_id,
        return_pct,
        *,
        realized=False,
    ):
        calls.append(
            (
                wallet_id,
                token_id,
                return_pct,
                realized,
            )
        )
        return {
            "state": "INSUFFICIENT_SAMPLE",
            "decision_authority": False,
            "execution_authority": False,
        }

    feed = RuntimeLearningOutcomeFeed(
        wallet_outcome_observer=observer,
        wallet_outcome_db_path=path,
    )

    result = feed.hydrate_wallet_outcomes()

    assert result["state"] == "READY"
    assert result["backfill"]["eligible"] == 1
    assert result["backfill"]["persisted"] == 1
    assert result["hydrated"] == 1

    assert calls == [
        (
            WALLET,
            "paper-position:1",
            12.5,
            True,
        )
    ]

    db = sqlite3.connect(path)

    row = db.execute(
        """
        SELECT
            wallet_uid,
            token_key,
            evidence_type,
            outcome_value,
            evidence_quality,
            provenance
        FROM wallet_outcome_evidence
        """
    ).fetchone()

    db.close()

    assert row == (
        WALLET,
        "0xtoken",
        "REALIZED_RETURN_PCT",
        12.5,
        1.0,
        "PAPER_MANAGER_CLOSE:paper-position:1",
    )


def test_backfill_is_deduplicated(tmp_path):
    path = tmp_path / "paper.db"
    make_db(path)

    db = sqlite3.connect(path)

    db.execute(
        """
        INSERT INTO paper_trades(
            id,
            token,
            closed_at,
            roi,
            opening_context_json,
            status
        )
        VALUES(2, '0xtoken2', ?, -0.05, ?, 'CLOSED')
        """,
        (
            "2026-09-08T12:01:00+00:00",
            json.dumps(
                eligible_context()
            ),
        ),
    )

    db.commit()
    db.close()

    feed = RuntimeLearningOutcomeFeed(
        wallet_outcome_observer=(
            lambda *args, **kwargs: {
                "state": "INSUFFICIENT_SAMPLE"
            }
        ),
        wallet_outcome_db_path=path,
    )

    first = feed.hydrate_wallet_outcomes()
    second = feed.hydrate_wallet_outcomes()

    assert first["backfill"]["persisted"] == 1
    assert second["backfill"]["persisted"] == 0

    db = sqlite3.connect(path)

    count = db.execute(
        """
        SELECT COUNT(*)
        FROM wallet_outcome_evidence
        """
    ).fetchone()[0]

    db.close()

    assert count == 1


def test_authority_remains_read_only(tmp_path):
    path = tmp_path / "paper.db"
    make_db(path)

    feed = RuntimeLearningOutcomeFeed(
        wallet_outcome_observer=(
            lambda *args, **kwargs: {
                "state": "UNKNOWN"
            }
        ),
        wallet_outcome_db_path=path,
    )

    result = feed.hydrate_wallet_outcomes()

    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["signing_authority"] is False
    assert result["execution_authority"] is False


def test_live_close_persists_real_token_and_close_time(tmp_path):
    path = tmp_path / "paper.db"
    make_db(path)

    calls = []

    def observer(
        wallet_id,
        token_id,
        return_pct,
        *,
        realized=False,
    ):
        calls.append(
            (
                wallet_id,
                token_id,
                return_pct,
                realized,
            )
        )
        return {
            "state": "INSUFFICIENT_SAMPLE",
            "decision_authority": False,
            "execution_authority": False,
        }

    feed = RuntimeLearningOutcomeFeed(
        wallet_outcome_observer=observer,
        wallet_outcome_db_path=path,
    )

    opening_context = eligible_context()
    opening_context["captured_at_entry"] = True
    opening_context["hindsight_reconstructed"] = False

    result = feed.observe_paper_close(
        position_id=9,
        token="0xreal-token",
        observed_at="2026-09-08T10:00:00+00:00",
        evaluated_at="2026-09-08T10:15:00+00:00",
        entry_price=1.0,
        exit_price=1.1,
        realized_return=0.10,
        close_reason="TAKE_PROFIT",
        opening_context=opening_context,
        wallet_id=WALLET,
    )

    assert result["state"] == "OBSERVED"

    db = sqlite3.connect(path)

    row = db.execute(
        """
        SELECT
            observed_at,
            token_key,
            outcome_value,
            provenance
        FROM wallet_outcome_evidence
        """
    ).fetchone()

    db.close()

    assert row == (
        "2026-09-08T10:15:00+00:00",
        "0xreal-token",
        10.0,
        "PAPER_MANAGER_CLOSE:paper-position:9",
    )

    assert calls == [
        (
            WALLET,
            "paper-position:9",
            10.0,
            True,
        )
    ]
