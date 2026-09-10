import sqlite3

import app.learning as learning


def _fail_schema_write(_self):
    raise AssertionError("schema write path must not run for a ready canonical DB")


def test_ready_canonical_watch_stores_open_under_external_write_lock(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "paper.db"

    probe_seed = learning._OriginalWatchProbeStore(db_path)
    snapshot_seed = learning._OriginalWatchProbeEntrySnapshotStore(db_path)
    probe_seed._db.close()
    snapshot_seed._db.close()

    canonical_key = db_path.resolve(strict=False).as_posix()
    monkeypatch.setattr(
        learning,
        "_CONFIGURED_PAPER_DB_KEY",
        canonical_key,
    )

    for cls in (
        learning._SerializedWatchProbeStore,
        learning._SerializedWatchProbeEntrySnapshotStore,
    ):
        monkeypatch.setattr(cls, "_canonical_instance", None)
        monkeypatch.setattr(cls, "_canonical_key", None)

    monkeypatch.setattr(
        learning._OriginalWatchProbeStore,
        "_ensure_schema",
        _fail_schema_write,
    )
    monkeypatch.setattr(
        learning._OriginalWatchProbeEntrySnapshotStore,
        "_ensure_schema",
        _fail_schema_write,
    )

    blocker = sqlite3.connect(db_path)
    blocker.execute("PRAGMA journal_mode=WAL")
    blocker.execute("BEGIN IMMEDIATE")

    probe = None
    snapshot = None
    try:
        probe = learning._SerializedWatchProbeStore(db_path)
        snapshot = learning._SerializedWatchProbeEntrySnapshotStore(db_path)

        assert probe._db.execute("SELECT 1").fetchone()[0] == 1
        assert snapshot._db.execute("SELECT 1").fetchone()[0] == 1
    finally:
        if probe is not None:
            probe._db.close()
        if snapshot is not None:
            snapshot._db.close()
        blocker.rollback()
        blocker.close()
