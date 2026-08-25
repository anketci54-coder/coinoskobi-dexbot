import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.universe.schema import (
    MARKET_COLD,
    canonical_address,
    canonical_chain,
    canonical_dex,
    canonical_discovery_branch,
)


DEFAULT_DB = Path("data/cache/cache.db")


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class UniverseRegistry:
    """Durable, provider-neutral PancakeSwap pool registry."""

    def __init__(self, db_path=DEFAULT_DB, *, connection=None):
        if connection is None:
            db_path = Path(db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(db_path)
            self._owns_connection = True
        else:
            self._owns_connection = False

        self.db = connection
        self.db.row_factory = sqlite3.Row
        self.migrate()

    def migrate(self):
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS universe_pool_registry(
                    chain TEXT NOT NULL,
                    dex TEXT NOT NULL,
                    pool TEXT NOT NULL,
                    token0 TEXT,
                    token1 TEXT,
                    fee_tier INTEGER,
                    factory TEXT NOT NULL,
                    creation_block INTEGER NOT NULL,
                    creation_tx TEXT,
                    created_at TEXT,
                    discovery_branch TEXT NOT NULL
                        CHECK(discovery_branch IN ('EXISTING','NEW')),
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    market_state TEXT NOT NULL DEFAULT 'COLD'
                        CHECK(market_state IN ('COLD','WARM','HOT')),
                    state_changed_at TEXT NOT NULL,
                    next_observation_at TEXT,
                    last_observation_at TEXT,
                    latest_liquidity_usd REAL,
                    latest_volume_24h REAL,
                    latest_price_usd REAL,
                    latest_txns_5m INTEGER,
                    latest_txns_1h INTEGER,
                    latest_txns_6h INTEGER,
                    latest_txns_24h INTEGER,
                    latest_change_5m REAL,
                    latest_change_1h REAL,
                    latest_change_6h REAL,
                    latest_change_24h REAL,
                    latest_snapshot_source TEXT,
                    latest_snapshot_at TEXT,
                    profile_json TEXT,
                    PRIMARY KEY(chain, dex, pool)
                )
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_universe_state_due
                ON universe_pool_registry(market_state, next_observation_at)
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_universe_dex_block
                ON universe_pool_registry(dex, creation_block)
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_universe_token0
                ON universe_pool_registry(token0)
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_universe_token1
                ON universe_pool_registry(token1)
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_universe_snapshot_at
                ON universe_pool_registry(latest_snapshot_at)
            """)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS universe_discovery_checkpoint(
                    chain TEXT NOT NULL,
                    dex TEXT NOT NULL,
                    factory TEXT NOT NULL,
                    event_kind TEXT NOT NULL,
                    last_scanned_block INTEGER NOT NULL,
                    last_finalized_block INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(chain, dex, factory, event_kind)
                )
            """)

    @staticmethod
    def _normalize_pool(row, observed_at):
        creation_block = int(row["creation_block"])
        if creation_block < 0:
            raise ValueError("creation block must be non-negative")

        fee_tier = row.get("fee_tier")
        if fee_tier is not None:
            fee_tier = int(fee_tier)
            if fee_tier < 0:
                raise ValueError("fee tier must be non-negative")

        profile = row.get("profile")
        profile_json = (
            json.dumps(profile, sort_keys=True, separators=(",", ":"))
            if profile is not None
            else None
        )

        return {
            "chain": canonical_chain(row.get("chain", "bsc")),
            "dex": canonical_dex(row["dex"]),
            "pool": canonical_address(row["pool"]),
            "token0": canonical_address(row.get("token0"), required=False),
            "token1": canonical_address(row.get("token1"), required=False),
            "fee_tier": fee_tier,
            "factory": canonical_address(row["factory"]),
            "creation_block": creation_block,
            "creation_tx": str(row.get("creation_tx") or "").strip().lower() or None,
            "created_at": row.get("created_at"),
            "discovery_branch": canonical_discovery_branch(
                row["discovery_branch"]
            ),
            "observed_at": str(row.get("observed_at") or observed_at),
            "next_observation_at": row.get("next_observation_at"),
            "profile_json": profile_json,
        }

    def ingest(self, pools, *, checkpoint=None, observed_at=None):
        """Atomically upsert a bounded discovery result and its checkpoint."""
        observed_at = str(observed_at or _utc_now())
        normalized = [
            self._normalize_pool(row, observed_at)
            for row in pools
        ]

        with self.db:
            for row in normalized:
                self.db.execute("""
                    INSERT INTO universe_pool_registry(
                        chain, dex, pool, token0, token1, fee_tier,
                        factory, creation_block, creation_tx, created_at,
                        discovery_branch, first_seen_at, last_seen_at,
                        market_state, state_changed_at,
                        next_observation_at, profile_json
                    ) VALUES(
                        :chain, :dex, :pool, :token0, :token1, :fee_tier,
                        :factory, :creation_block, :creation_tx, :created_at,
                        :discovery_branch, :observed_at, :observed_at,
                        'COLD', :observed_at,
                        :next_observation_at, :profile_json
                    )
                    ON CONFLICT(chain, dex, pool) DO UPDATE SET
                        token0=COALESCE(excluded.token0, token0),
                        token1=COALESCE(excluded.token1, token1),
                        fee_tier=COALESCE(excluded.fee_tier, fee_tier),
                        creation_tx=COALESCE(excluded.creation_tx, creation_tx),
                        created_at=COALESCE(excluded.created_at, created_at),
                        last_seen_at=excluded.last_seen_at,
                        next_observation_at=COALESCE(
                            excluded.next_observation_at,
                            next_observation_at
                        ),
                        profile_json=COALESCE(excluded.profile_json, profile_json)
                """, row)

            if checkpoint is not None:
                self._write_checkpoint(checkpoint, observed_at)

        return len(normalized)

    def _write_checkpoint(self, row, updated_at):
        last_scanned = int(row["last_scanned_block"])
        last_finalized = int(row["last_finalized_block"])
        if last_scanned < 0 or last_finalized < 0:
            raise ValueError("checkpoint blocks must be non-negative")
        if last_finalized > last_scanned:
            raise ValueError("finalized block cannot exceed scanned block")

        values = {
            "chain": canonical_chain(row.get("chain", "bsc")),
            "dex": canonical_dex(row["dex"]),
            "factory": canonical_address(row["factory"]),
            "event_kind": str(row["event_kind"]).strip().upper(),
            "last_scanned_block": last_scanned,
            "last_finalized_block": last_finalized,
            "updated_at": updated_at,
        }
        if not values["event_kind"]:
            raise ValueError("event kind required")

        self.db.execute("""
            INSERT INTO universe_discovery_checkpoint(
                chain, dex, factory, event_kind,
                last_scanned_block, last_finalized_block, updated_at
            ) VALUES(
                :chain, :dex, :factory, :event_kind,
                :last_scanned_block, :last_finalized_block, :updated_at
            )
            ON CONFLICT(chain, dex, factory, event_kind) DO UPDATE SET
                last_scanned_block=excluded.last_scanned_block,
                last_finalized_block=excluded.last_finalized_block,
                updated_at=excluded.updated_at
        """, values)

    def due_observations(self, *, now=None, limit):
        limit = int(limit)
        if limit < 1:
            raise ValueError("positive explicit limit required")

        now = str(now or _utc_now())
        rows = self.db.execute("""
            SELECT *
            FROM universe_pool_registry
            WHERE next_observation_at IS NULL
               OR next_observation_at <= ?
            ORDER BY
                CASE market_state
                    WHEN 'HOT' THEN 0
                    WHEN 'WARM' THEN 1
                    ELSE 2
                END,
                next_observation_at,
                creation_block
            LIMIT ?
        """, (now, limit)).fetchall()
        return [dict(row) for row in rows]

    def get_pool(self, chain, dex, pool):
        row = self.db.execute("""
            SELECT *
            FROM universe_pool_registry
            WHERE chain=? AND dex=? AND pool=?
        """, (
            canonical_chain(chain),
            canonical_dex(dex),
            canonical_address(pool),
        )).fetchone()
        return dict(row) if row else None

    def checkpoint(self, chain, dex, factory, event_kind):
        row = self.db.execute("""
            SELECT *
            FROM universe_discovery_checkpoint
            WHERE chain=? AND dex=? AND factory=? AND event_kind=?
        """, (
            canonical_chain(chain),
            canonical_dex(dex),
            canonical_address(factory),
            str(event_kind).strip().upper(),
        )).fetchone()
        return dict(row) if row else None

    def count(self):
        return int(self.db.execute(
            "SELECT COUNT(*) FROM universe_pool_registry"
        ).fetchone()[0])

    def close(self):
        if self._owns_connection:
            self.db.close()

