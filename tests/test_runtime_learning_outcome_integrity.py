import json
import sqlite3

from app.learning.runtime_outcome_feed import (
    RuntimeLearningOutcomeFeed,
)


CREATED_37 = "2026-09-13T15:18:35.118255+00:00"
CLOSED_37 = "2026-09-13T16:25:18.506054+00:00"


def _registry(path):
    path.write_text(
        json.dumps({
            "version": 1,
            "exclusions": [
                {
                    "source_table": "paper_trades",
                    "position_id": 37,
                    "created_at": CREATED_37,
                    "closed_at": CLOSED_37,
                    "reason": (
                        "BUG_CONTAMINATED_RUNTIME_"
                        "LIFECYCLE_STARVATION_PR147"
                    ),
                }
            ],
        }),
        encoding="utf-8",
    )
    return path


def _observe(feed, *, position_id=37, created_at=CREATED_37, closed_at=CLOSED_37):
    return feed.observe_paper_close(
        position_id=position_id,
        token="0xtoken",
        observed_at=created_at,
        evaluated_at=closed_at,
        entry_price=1.0,
        exit_price=0.9,
        realized_return=-0.10,
        close_reason="MATHEMATICAL_TREND_FLOOR",
        opening_context=None,
    )


def _wallet_db(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE paper_trades (
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            closed_at TEXT,
            token TEXT,
            roi REAL,
            status TEXT,
            opening_context_json TEXT
        );

        CREATE TABLE wallet_discovery_registry (
            wallet_uid TEXT PRIMARY KEY
        );

        CREATE TABLE wallet_outcome_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_uid TEXT,
            observed_at TEXT,
            token_key TEXT,
            evidence_type TEXT,
            outcome_value REAL,
            evidence_quality REAL,
            provenance TEXT
        );
        """
    )
    return db


def _actor_context(wallet):
    return json.dumps({
        "actor_identity": {
            "wallet_id": wallet,
            "identity_source": "TRANSACTION_FROM_ONLY",
            "hindsight_reconstructed": False,
        }
    })


def test_contaminated_direct_close_never_enters_learning(tmp_path):
    registry = _registry(tmp_path / "exclusions.json")
    wallet_calls = []

    feed = RuntimeLearningOutcomeFeed(
        outcome_exclusions_path=registry,
        wallet_outcome_observer=lambda *args, **kwargs: wallet_calls.append(
            (args, kwargs)
        ) or {"state": "OBSERVED"},
    )

    result = _observe(feed)

    assert result["state"] == "EXCLUDED"
    assert result["payload"]["outcome_integrity"]["state"] == "BUG_CONTAMINATED"
    assert feed.event_count == 0
    assert feed.accepted_count == 0
    assert feed.memory.size == 0
    assert feed.excluded_count == 1
    assert wallet_calls == []


def test_missing_registry_blocks_learning_fail_closed(tmp_path):
    feed = RuntimeLearningOutcomeFeed(
        outcome_exclusions_path=tmp_path / "missing.json",
    )

    result = _observe(feed, position_id=38)

    assert result["state"] == "INTEGRITY_BLOCKED"
    assert feed.event_count == 0
    assert feed.accepted_count == 0
    assert feed.memory.size == 0
    assert feed.integrity_blocked_count == 1


def test_clean_outcome_preserves_existing_learning_path(tmp_path):
    registry = _registry(tmp_path / "exclusions.json")
    feed = RuntimeLearningOutcomeFeed(
        outcome_exclusions_path=registry,
        min_samples=1,
    )

    result = _observe(
        feed,
        position_id=38,
        created_at="2026-09-13T17:00:00+00:00",
        closed_at="2026-09-13T17:05:00+00:00",
    )

    assert result["state"] == "OBSERVED"
    assert result["payload"]["outcome_integrity"]["state"] == "TRUSTED"
    assert feed.event_count == 1
    assert feed.accepted_count == 1
    assert feed.memory.size == 1


def test_wallet_backfill_skips_contaminated_but_keeps_trusted(tmp_path):
    registry = _registry(tmp_path / "exclusions.json")
    db_path = tmp_path / "paper.db"
    db = _wallet_db(db_path)

    db.executemany(
        "INSERT INTO wallet_discovery_registry(wallet_uid) VALUES (?)",
        [("0xwallet37",), ("0xwallet38",)],
    )
    db.executemany(
        """
        INSERT INTO paper_trades(
            id, created_at, closed_at, token, roi, status,
            opening_context_json
        ) VALUES (?, ?, ?, ?, ?, 'CLOSED', ?)
        """,
        [
            (
                37,
                CREATED_37,
                CLOSED_37,
                "0xtoken37",
                -0.10,
                _actor_context("0xwallet37"),
            ),
            (
                38,
                "2026-09-13T17:00:00+00:00",
                "2026-09-13T17:05:00+00:00",
                "0xtoken38",
                0.20,
                _actor_context("0xwallet38"),
            ),
        ],
    )
    db.commit()
    db.close()

    feed = RuntimeLearningOutcomeFeed(
        outcome_exclusions_path=registry,
        wallet_outcome_db_path=db_path,
    )

    result = feed._backfill_wallet_outcomes()

    assert result["state"] == "READY"
    assert result["scanned"] == 2
    assert result["excluded"] == 1
    assert result["eligible"] == 1
    assert result["persisted"] == 1

    db = sqlite3.connect(db_path)
    provenances = [
        row[0]
        for row in db.execute(
            "SELECT provenance FROM wallet_outcome_evidence ORDER BY evidence_id"
        ).fetchall()
    ]
    db.close()

    assert provenances == [
        "PAPER_MANAGER_CLOSE:paper-position:38"
    ]


def test_hydration_never_replays_preexisting_contaminated_evidence(tmp_path):
    registry = _registry(tmp_path / "exclusions.json")
    db_path = tmp_path / "paper.db"
    db = _wallet_db(db_path)

    db.executemany(
        """
        INSERT INTO paper_trades(
            id, created_at, closed_at, token, roi, status,
            opening_context_json
        ) VALUES (?, ?, ?, ?, ?, 'CLOSED', '{}')
        """,
        [
            (37, CREATED_37, CLOSED_37, "0xtoken37", -0.10),
            (
                38,
                "2026-09-13T17:00:00+00:00",
                "2026-09-13T17:05:00+00:00",
                "0xtoken38",
                0.20,
            ),
        ],
    )
    db.executemany(
        """
        INSERT INTO wallet_outcome_evidence(
            wallet_uid, observed_at, token_key,
            evidence_type, outcome_value, evidence_quality, provenance
        ) VALUES (?, ?, ?, 'REALIZED_RETURN_PCT', ?, 1.0, ?)
        """,
        [
            (
                "0xwallet37",
                CLOSED_37,
                "0xtoken37",
                -10.0,
                "PAPER_MANAGER_CLOSE:paper-position:37",
            ),
            (
                "0xwallet38",
                "2026-09-13T17:05:00+00:00",
                "0xtoken38",
                20.0,
                "PAPER_MANAGER_CLOSE:paper-position:38",
            ),
        ],
    )
    db.commit()
    db.close()

    calls = []

    def observer(wallet_id, token_id, return_pct, realized=False):
        calls.append(
            (wallet_id, token_id, return_pct, realized)
        )
        return {"state": "OBSERVED"}

    feed = RuntimeLearningOutcomeFeed(
        outcome_exclusions_path=registry,
        wallet_outcome_db_path=db_path,
        wallet_outcome_observer=observer,
    )

    result = feed.hydrate_wallet_outcomes()

    assert result["state"] == "READY"
    assert result["excluded"] == 1
    assert result["hydrated"] == 1
    assert calls == [
        (
            "0xwallet38",
            "paper-position:38",
            20.0,
            True,
        )
    ]

    db = sqlite3.connect(db_path)
    count = db.execute(
        "SELECT COUNT(*) FROM wallet_outcome_evidence"
    ).fetchone()[0]
    db.close()

    assert count == 2
