import csv
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def _build_replay_db(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE universe_pool_registry (
            chain TEXT,
            dex TEXT,
            pool TEXT,
            token0 TEXT,
            token1 TEXT
        );

        CREATE TABLE universe_seismic_evaluation_v1 (
            id INTEGER PRIMARY KEY,
            chain TEXT,
            dex TEXT,
            pool TEXT,
            observed_at REAL,
            previous_state TEXT,
            next_state TEXT,
            score REAL,
            price_z REAL,
            volume_z REAL,
            txns_z REAL,
            liquidity_ratio REAL,
            evidence_count INTEGER,
            reason TEXT
        );

        CREATE TABLE universe_market_observation_v1 (
            id INTEGER PRIMARY KEY,
            chain TEXT,
            dex TEXT,
            pool TEXT,
            source TEXT,
            observed_at REAL,
            price_usd REAL,
            liquidity_usd REAL,
            volume_m5_usd REAL,
            buys_m5 INTEGER,
            sells_m5 INTEGER,
            txns_m5 INTEGER,
            change_m5 REAL
        );
        """
    )

    pools = [
        (
            "0xpool1",
            "0xtoken1",
            1_000.0,
            1.0,
        ),
        (
            "0xpool2",
            "0xtoken2",
            1_100.0,
            2.0,
        ),
    ]

    for index, (
        pool,
        token,
        event_time,
        price,
    ) in enumerate(pools, 1):
        db.execute(
            """
            INSERT INTO universe_pool_registry (
                chain,dex,pool,token0,token1
            )
            VALUES ('bsc','pancakeswap_v2',?,?,?)
            """,
            (
                pool,
                token,
                "0xquote",
            ),
        )
        db.execute(
            """
            INSERT INTO universe_seismic_evaluation_v1 (
                id,chain,dex,pool,observed_at,
                previous_state,next_state,score,
                price_z,volume_z,txns_z,
                liquidity_ratio,evidence_count,reason
            )
            VALUES (
                ?,'bsc','pancakeswap_v2',?,?,
                'COLD','HOT',1.0,
                1.0,1.0,1.0,
                1.0,5,'TEST'
            )
            """,
            (
                index,
                pool,
                event_time,
            ),
        )

        for offset, multiplier in (
            (0.0, 1.0),
            (420.0, 1.1),
            (2_220.0, 1.2),
        ):
            db.execute(
                """
                INSERT INTO universe_market_observation_v1 (
                    chain,dex,pool,source,observed_at,
                    price_usd,liquidity_usd,volume_m5_usd,
                    buys_m5,sells_m5,txns_m5,change_m5
                )
                VALUES (
                    'bsc','pancakeswap_v2',?,'TEST',?,
                    ?,100000,10000,
                    10,2,12,1.0
                )
                """,
                (
                    pool,
                    event_time + offset,
                    price * multiplier,
                ),
            )

    db.commit()
    db.close()


def test_replay_streams_pool_histories_without_changing_results(
    tmp_path,
):
    db_path = tmp_path / "cache.db"
    out_dir = tmp_path / "out"
    _build_replay_db(db_path)

    # Simulate live rows arriving after a frozen replay boundary.
    db = sqlite3.connect(db_path)
    db.execute(
        """
        INSERT INTO universe_pool_registry (
            chain,dex,pool,token0,token1
        )
        VALUES ('bsc','pancakeswap_v2','0xpool3','0xtoken3','0xquote')
        """
    )
    db.execute(
        """
        INSERT INTO universe_seismic_evaluation_v1 (
            id,chain,dex,pool,observed_at,
            previous_state,next_state,score,
            price_z,volume_z,txns_z,
            liquidity_ratio,evidence_count,reason
        )
        VALUES (
            3,'bsc','pancakeswap_v2','0xpool3',1200,
            'COLD','HOT',1.0,
            1.0,1.0,1.0,
            1.0,5,'LATE'
        )
        """
    )
    for observed_at, price in (
        (1200.0, 3.0),
        (1620.0, 3.3),
        (3420.0, 3.6),
    ):
        db.execute(
            """
            INSERT INTO universe_market_observation_v1 (
                chain,dex,pool,source,observed_at,
                price_usd,liquidity_usd,volume_m5_usd,
                buys_m5,sells_m5,txns_m5,change_m5
            )
            VALUES (
                'bsc','pancakeswap_v2','0xpool3','TEST',?,
                ?,100000,10000,
                10,2,12,1.0
            )
            """,
            (observed_at, price),
        )
    db.commit()
    db.close()

    script = (
        Path(__file__).resolve().parents[1]
        / "lab"
        / "opportunity_replay_v1"
        / "build_dataset.py"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db",
            str(db_path),
            "--decision-delay-seconds",
            "420",
            "--seismic-max-id",
            "2",
            "--observation-max-id",
            "6",
            "--out-dir",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(
        (out_dir / "summary.json").read_text()
    )
    assert summary["read_only"] is True
    assert summary["decision_delay_seconds"] == 420
    assert summary["seismic_max_id"] == 2
    assert summary["observation_max_id"] == 6
    assert summary["event_count"] == 2
    assert summary["entry_state_counts"] == {
        "HOT": 2,
    }

    with (out_dir / "events.csv").open(
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert [row["event_id"] for row in rows] == [
        "1",
        "2",
    ]
    assert all(
        float(row["pre_decision_return_pct"]) > 0
        for row in rows
    )

    assert "TRANSITIONS_LOADED replay_events=2 relevant_pools=2" in (
        completed.stdout
    )
    assert "RELEVANT_DATA_LOADED" in completed.stdout

    db = sqlite3.connect(db_path)
    assert db.execute(
        "SELECT COUNT(*) FROM universe_market_observation_v1"
    ).fetchone()[0] == 9
    db.close()
