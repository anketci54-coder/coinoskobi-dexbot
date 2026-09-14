from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

VALID_CONTROL_MODES = {
    "AUTO",
    "MANUAL",
}

DEFAULT_CONTROL_MODE = "AUTO"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path,
        timeout=30,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(
        "PRAGMA busy_timeout=30000"
    )
    return conn


def ensure_control_mode_schema(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS
        paper_runtime_control(
            id INTEGER PRIMARY KEY
                CHECK(id = 1),
            control_mode TEXT NOT NULL
                CHECK(
                    control_mode IN (
                        'AUTO',
                        'MANUAL'
                    )
                ),
            updated_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.execute(
        """
        INSERT OR IGNORE INTO
        paper_runtime_control(
            id,
            control_mode
        )
        VALUES(
            1,
            'AUTO'
        )
        """
    )


def get_control_mode_from_connection(
    connection: sqlite3.Connection,
) -> str:
    table = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table'
          AND name='paper_runtime_control'
        LIMIT 1
        """
    ).fetchone()

    if table is None:
        return DEFAULT_CONTROL_MODE

    row = connection.execute(
        """
        SELECT control_mode
        FROM paper_runtime_control
        WHERE id=1
        """
    ).fetchone()

    if row is None:
        return DEFAULT_CONTROL_MODE

    mode = str(
        row[0]
    ).strip().upper()

    if mode not in VALID_CONTROL_MODES:
        return DEFAULT_CONTROL_MODE

    return mode


def get_control_mode(
    db_path: Path,
) -> str:
    connection = _connect(db_path)

    try:
        ensure_control_mode_schema(
            connection
        )

        row = connection.execute(
            """
            SELECT control_mode
            FROM paper_runtime_control
            WHERE id=1
            """
        ).fetchone()

        connection.commit()

        mode = str(
            row["control_mode"]
            if row is not None
            else DEFAULT_CONTROL_MODE
        ).strip().upper()

        if mode not in VALID_CONTROL_MODES:
            return DEFAULT_CONTROL_MODE

        return mode

    finally:
        connection.close()


def set_control_mode(
    db_path: Path,
    mode: Any,
) -> str:
    normalized = str(
        mode or ""
    ).strip().upper()

    if normalized not in VALID_CONTROL_MODES:
        raise ValueError(
            "CONTROL_MODE_INVALID"
        )

    connection = _connect(db_path)

    try:
        ensure_control_mode_schema(
            connection
        )

        connection.execute(
            """
            UPDATE paper_runtime_control
            SET
                control_mode=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=1
            """,
            (
                normalized,
            ),
        )

        connection.commit()

        return normalized

    finally:
        connection.close()


def auto_entry_enabled(
    db_path: Path,
) -> bool:
    return (
        get_control_mode(
            db_path
        )
        == "AUTO"
    )
