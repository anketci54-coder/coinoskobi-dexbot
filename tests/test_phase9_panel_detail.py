import json
import sqlite3

from app.dex.phase9_panel_detail import (
    DEFAULT_DETAIL_LIMIT,
    SUMMARY_KEY,
    TRIGGER_NAMES,
    apply_phase9_panel_detail,
)


def _db(tmp_path):
    path = tmp_path / "paper.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE wallet_discovery_registry (
            wallet_uid TEXT,
            chain TEXT,
            address TEXT,
            first_seen_at REAL,
            last_seen_at REAL,
            discovery_source TEXT,
            freshness_state TEXT,
            lifecycle_state TEXT
        );

        CREATE TABLE wallet_success_score (
            wallet_uid TEXT,
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

        CREATE TABLE whale_activity_snapshot (
            wallet_uid TEXT,
            generated_at REAL,
            whale_state TEXT,
            direction TEXT,
            activity_score REAL,
            evidence_count INTEGER
        );
        """
    )
    con.commit()
    con.close()
    return path


def _wallet(index):
    return f"bsc:0x{index:040x}"


def _insert_wallet(con, wallet, seen, source="TRANSACTION_FROM_ONLY"):
    chain, address = wallet.split(":", 1)
    con.execute(
        """
        INSERT INTO wallet_discovery_registry(
            wallet_uid, chain, address, first_seen_at, last_seen_at,
            discovery_source, freshness_state, lifecycle_state
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            wallet,
            chain,
            address,
            seen,
            seen,
            source,
            "FRESH",
            "ACTIVE",
        ),
    )


def _summary(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM intelligence_summary_readmodel WHERE summary_key=?",
        (SUMMARY_KEY,),
    ).fetchone()
    con.close()
    return dict(row)


def test_detail_publishes_only_real_phase9_wallets(tmp_path):
    path = _db(tmp_path)
    real = _wallet(1)
    fake = _wallet(2)

    con = sqlite3.connect(path)
    _insert_wallet(con, real, 1000.0)
    _insert_wallet(con, fake, 1001.0, source="ROUTER_GUESS")
    con.commit()
    con.close()

    result = apply_phase9_panel_detail(path)
    summary = _summary(path)
    details = json.loads(summary["wallet_details_json"])

    assert result["tracked_wallets"] == 1
    assert result["detail_rows"] == 1
    assert result["triggers_installed"] == len(TRIGGER_NAMES)
    assert result["panel_read_only"] is True
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False

    assert details == [
        {
            "address": real.split(":", 1)[1],
            "chain": "bsc",
            "discovery_source": "TRANSACTION_FROM_ONLY",
            "first_seen_at": 1000.0,
            "last_seen_at": 1000.0,
            "success_sample_depth": None,
            "success_state": "UNKNOWN",
            "wallet_uid": real,
            "whale_direction": "UNKNOWN",
            "whale_state": "UNKNOWN",
        }
    ]


def test_success_and_whale_detail_require_durable_rows(tmp_path):
    path = _db(tmp_path)
    wallet = _wallet(3)

    con = sqlite3.connect(path)
    _insert_wallet(con, wallet, 2000.0)
    con.execute(
        """
        INSERT INTO wallet_success_score(
            wallet_uid, calculated_at, sample_depth, qualification_state
        ) VALUES(?,?,?,?)
        """,
        (wallet, 2001.0, 27, "SUCCESSFUL"),
    )
    con.execute(
        """
        INSERT INTO whale_activity_snapshot(
            wallet_uid, generated_at, whale_state, direction,
            activity_score, evidence_count
        ) VALUES(?,?,?,?,?,?)
        """,
        (wallet, 2002.0, "WHALE_CONFIRMED", "BUY", 0.0, 1),
    )
    con.commit()
    con.close()

    result = apply_phase9_panel_detail(path)
    summary = _summary(path)
    details = json.loads(summary["wallet_details_json"])

    assert result["successful_wallets"] == 1
    assert result["active_whales"] == 1
    assert details[0]["success_state"] == "SUCCESSFUL"
    assert details[0]["success_sample_depth"] == 27
    assert details[0]["whale_state"] == "WHALE_CONFIRMED"
    assert details[0]["whale_direction"] == "BUY"


def test_detail_is_bounded_and_orders_recent_first(tmp_path):
    path = _db(tmp_path)
    con = sqlite3.connect(path)

    for index in range(1, 20):
        _insert_wallet(con, _wallet(index), float(index))

    con.commit()
    con.close()

    result = apply_phase9_panel_detail(path)
    summary = _summary(path)
    details = json.loads(summary["wallet_details_json"])

    assert result["tracked_wallets"] == 19
    assert result["detail_rows"] == DEFAULT_DETAIL_LIMIT
    assert len(details) == DEFAULT_DETAIL_LIMIT
    assert details[0]["wallet_uid"] == _wallet(19)
    assert details[-1]["wallet_uid"] == _wallet(8)


def test_summary_refreshes_after_future_registry_update(tmp_path):
    path = _db(tmp_path)
    wallet = _wallet(25)

    con = sqlite3.connect(path)
    _insert_wallet(con, wallet, 3000.0)
    con.commit()
    con.close()

    apply_phase9_panel_detail(path)

    con = sqlite3.connect(path)
    con.execute(
        """
        UPDATE wallet_discovery_registry
        SET last_seen_at=4000.0
        WHERE wallet_uid=?
        """,
        (wallet,),
    )
    con.commit()
    con.close()

    summary = _summary(path)
    details = json.loads(summary["wallet_details_json"])

    assert details[0]["last_seen_at"] == 4000.0


def test_success_and_whale_triggers_refresh_summary(tmp_path):
    path = _db(tmp_path)
    wallet = _wallet(30)

    con = sqlite3.connect(path)
    _insert_wallet(con, wallet, 5000.0)
    con.commit()
    con.close()

    apply_phase9_panel_detail(path)

    con = sqlite3.connect(path)
    con.execute(
        """
        INSERT INTO wallet_success_score(
            wallet_uid, calculated_at, sample_depth, qualification_state
        ) VALUES(?,?,?,?)
        """,
        (wallet, 5001.0, 31, "SUCCESSFUL"),
    )
    con.execute(
        """
        INSERT INTO whale_activity_snapshot(
            wallet_uid, generated_at, whale_state, direction,
            activity_score, evidence_count
        ) VALUES(?,?,?,?,?,?)
        """,
        (wallet, 5002.0, "WHALE_CONFIRMED", "SELL", 0.0, 1),
    )
    con.commit()
    con.close()

    summary = _summary(path)
    details = json.loads(summary["wallet_details_json"])

    assert summary["successful_wallets"] == 1
    assert summary["active_whales"] == 1
    assert details[0]["success_state"] == "SUCCESSFUL"
    assert details[0]["whale_state"] == "WHALE_CONFIRMED"
    assert details[0]["whale_direction"] == "SELL"
