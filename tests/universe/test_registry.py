import sqlite3

import pytest

from app.universe.registry import UniverseRegistry


POOL = "0x" + "1" * 40
TOKEN0 = "0x" + "2" * 40
TOKEN1 = "0x" + "3" * 40
FACTORY = "0x" + "4" * 40


def pool_row(branch="EXISTING", **overrides):
    row = {
        "chain": "bsc",
        "dex": "pancakeswap_v2",
        "pool": POOL,
        "token0": TOKEN0,
        "token1": TOKEN1,
        "factory": FACTORY,
        "creation_block": 100,
        "discovery_branch": branch,
        "created_at": "2020-01-01T00:00:00+00:00",
        "profile": {"liquidity_usd": 1.0, "age_hours": 50000},
    }
    row.update(overrides)
    return row


def checkpoint(**overrides):
    row = {
        "chain": "bsc",
        "dex": "pancakeswap_v2",
        "factory": FACTORY,
        "event_kind": "PAIR_CREATED",
        "last_scanned_block": 120,
        "last_finalized_block": 110,
    }
    row.update(overrides)
    return row


def test_clean_and_repeated_migration_are_idempotent(tmp_path):
    path = tmp_path / "cache.db"
    first = UniverseRegistry(path)
    first.close()
    second = UniverseRegistry(path)
    assert second.count() == 0


def test_migration_preserves_existing_cache_tables(tmp_path):
    path = tmp_path / "cache.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE gecko_pool_cache(pool TEXT PRIMARY KEY)")
    db.execute("INSERT INTO gecko_pool_cache VALUES('kept')")
    db.commit()
    db.close()

    registry = UniverseRegistry(path)
    value = registry.db.execute(
        "SELECT pool FROM gecko_pool_cache"
    ).fetchone()[0]
    assert value == "kept"


def test_existing_and_new_discovery_collapse_to_one_row(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([pool_row("EXISTING")], observed_at="2026-01-01T00:00:00+00:00")
    registry.ingest([pool_row("NEW")], observed_at="2026-01-02T00:00:00+00:00")

    assert registry.count() == 1
    row = registry.get_pool("bsc", "pancakeswap_v2", POOL.upper())
    assert row["market_state"] == "COLD"
    assert row["discovery_branch"] == "EXISTING"
    assert row["last_seen_at"] == "2026-01-02T00:00:00+00:00"


def test_pool_and_checkpoint_commit_together(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([pool_row()], checkpoint=checkpoint())

    assert registry.count() == 1
    saved = registry.checkpoint(
        "bsc", "pancakeswap_v2", FACTORY, "PAIR_CREATED"
    )
    assert saved["last_scanned_block"] == 120


def test_invalid_checkpoint_rolls_back_pool_batch(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")

    with pytest.raises(ValueError):
        registry.ingest(
            [pool_row()],
            checkpoint=checkpoint(last_finalized_block=121),
        )

    assert registry.count() == 0


def test_due_reads_require_and_obey_explicit_bound(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    rows = [
        pool_row(pool="0x" + f"{value:040x}", creation_block=value)
        for value in range(1, 6)
    ]
    registry.ingest(rows)

    assert len(registry.due_observations(limit=2)) == 2
    with pytest.raises(ValueError):
        registry.due_observations(limit=0)


def test_age_and_liquidity_profile_never_exclude_pool(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([pool_row()])

    assert registry.count() == 1
    assert registry.get_pool("bsc", "pancakeswap_v2", POOL)[
        "profile_json"
    ] == '{"age_hours":50000,"liquidity_usd":1.0}'


def test_only_pancake_v2_v3_and_valid_addresses_are_accepted(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([pool_row(dex="pancakeswap_v3", fee_tier=2500)])

    with pytest.raises(ValueError):
        registry.ingest([pool_row(dex="four-meme")])
    with pytest.raises(ValueError):
        registry.ingest([pool_row(pool="not-an-address")])

