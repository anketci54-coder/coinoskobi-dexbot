import sqlite3
from datetime import datetime, timezone

from app.learning.runtime_performance_observer import (
    RuntimePerformanceObserver,
)


SINCE = "2026-08-25T12:52:09+00:00"
SINCE_EPOCH = datetime(
    2026, 8, 25, 12, 52, 9,
    tzinfo=timezone.utc,
).timestamp()


def _db(path):
    db = sqlite3.connect(path)

    db.execute(
        """
        CREATE TABLE paper_trades(
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            closed_at TEXT,
            token TEXT,
            symbol TEXT,
            pool TEXT,
            dex TEXT,
            status TEXT,
            trade_policy TEXT,
            entry_price REAL,
            current_price REAL,
            exit_price REAL,
            highest_price REAL,
            lowest_price REAL,
            entry_amount_usdt REAL,
            risk_amount_usdt REAL,
            position_size_pct REAL,
            sizing_reason TEXT,
            gross_pnl_usdt REAL,
            net_pnl_usdt REAL,
            roi REAL,
            close_reason TEXT,
            tp1_done INTEGER,
            tp2_done INTEGER,
            runner_active INTEGER
        )
        """
    )

    db.execute(
        """
        CREATE TABLE candidate_decision_history(
            id INTEGER PRIMARY KEY,
            token TEXT NOT NULL,
            pool TEXT NOT NULL,
            observed_at REAL NOT NULL,
            decision_action TEXT NOT NULL,
            reason TEXT,
            signal_state TEXT NOT NULL,
            entry_price REAL,
            fingerprint TEXT,
            context_json TEXT NOT NULL DEFAULT '{}',
            promotion INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    db.execute(
        """
        CREATE TABLE counterfactual_observations(
            id INTEGER PRIMARY KEY,
            token TEXT NOT NULL,
            pool TEXT NOT NULL,
            observed_at REAL NOT NULL,
            entry_price REAL NOT NULL,
            signal_state TEXT NOT NULL,
            candidate_action TEXT NOT NULL,
            context_json TEXT NOT NULL DEFAULT '{}',
            last_observed_at REAL,
            last_price REAL,
            max_price REAL,
            min_price REAL,
            price_5m REAL,
            return_5m REAL,
            observed_5m_at REAL,
            price_15m REAL,
            return_15m REAL,
            observed_15m_at REAL,
            price_30m REAL,
            return_30m REAL,
            observed_30m_at REAL,
            price_60m REAL,
            return_60m REAL,
            observed_60m_at REAL,
            completed_at REAL,
            price_6h REAL,
            return_6h REAL,
            observed_6h_at REAL,
            mfe_6h REAL,
            mae_6h REAL,
            price_24h REAL,
            return_24h REAL,
            observed_24h_at REAL,
            mfe_24h REAL,
            mae_24h REAL,
            mfe_5m REAL,
            mae_5m REAL,
            mfe_15m REAL,
            mae_15m REAL,
            mfe_30m REAL,
            mae_30m REAL,
            mfe_60m REAL,
            mae_60m REAL,
            decision_history_id INTEGER,
            promoted_at REAL,
            first_2x_at REAL,
            first_5x_at REAL,
            first_10x_at REAL,
            first_50pct_loss_at REAL,
            first_90pct_loss_at REAL
        )
        """
    )

    return db


def _insert_trade(
    db,
    *,
    trade_id,
    created_at,
    token,
    symbol,
    pnl,
    status="CLOSED",
):
    db.execute(
        """
        INSERT INTO paper_trades(
            id, created_at, closed_at, token, symbol, pool, dex,
            status, trade_policy, entry_price, current_price,
            exit_price, highest_price, lowest_price,
            entry_amount_usdt, risk_amount_usdt,
            position_size_pct, sizing_reason,
            gross_pnl_usdt, net_pnl_usdt, roi,
            close_reason, tp1_done, tp2_done, runner_active
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            trade_id,
            created_at,
            created_at if status == "CLOSED" else None,
            token,
            symbol,
            "0xpool" + str(trade_id),
            "pancakeswap_v2",
            status,
            "VUR_KAC",
            1.0,
            1.1,
            1.1 if status == "CLOSED" else None,
            1.4,
            0.8,
            100.0,
            5.0,
            0.01,
            "TEST",
            pnl,
            pnl,
            pnl / 100.0,
            "TEST_CLOSE" if status == "CLOSED" else None,
            0,
            0,
            0,
        ),
    )


def _insert_decision(
    db,
    *,
    decision_id,
    token,
    pool,
    at,
    action,
    reason,
    promotion=0,
    context="{}",
):
    db.execute(
        """
        INSERT INTO candidate_decision_history(
            id, token, pool, observed_at, decision_action,
            reason, signal_state, entry_price, fingerprint,
            context_json, promotion
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            decision_id,
            token,
            pool,
            at,
            action,
            reason,
            "POSITIVE" if action == "PAPER_BUY" else "UNKNOWN",
            1.0,
            f"fp-{decision_id}",
            context,
            promotion,
        ),
    )


def _insert_cf(
    db,
    *,
    cf_id,
    decision_id,
    token,
    pool,
    observed_at,
    promoted_at=None,
    first_2x_at=None,
    first_5x_at=None,
    first_10x_at=None,
    first_50pct_loss_at=None,
    first_90pct_loss_at=None,
    completed_at=None,
):
    db.execute(
        """
        INSERT INTO counterfactual_observations(
            id, token, pool, observed_at, entry_price,
            signal_state, candidate_action, context_json,
            last_observed_at, last_price, max_price, min_price,
            price_5m, return_5m, observed_5m_at,
            price_15m, return_15m, observed_15m_at,
            price_30m, return_30m, observed_30m_at,
            price_60m, return_60m, observed_60m_at,
            completed_at,
            price_6h, return_6h, observed_6h_at, mfe_6h, mae_6h,
            price_24h, return_24h, observed_24h_at, mfe_24h, mae_24h,
            mfe_5m, mae_5m, mfe_15m, mae_15m,
            mfe_30m, mae_30m, mfe_60m, mae_60m,
            decision_history_id, promoted_at,
            first_2x_at, first_5x_at, first_10x_at,
            first_50pct_loss_at, first_90pct_loss_at
        )
        VALUES(
            ?,?,?,?,?,?,?,?,
            ?,?,?,?,
            ?,?,?,
            ?,?,?,
            ?,?,?,
            ?,?,?,
            ?,
            ?,?,?,?,?,
            ?,?,?,?,?,
            ?,?,?,?,
            ?,?,?,?,
            ?,?,
            ?,?,?,
            ?,?
        )
        """,
        (
            cf_id,
            token,
            pool,
            observed_at,
            1.0,
            "UNKNOWN",
            "REJECT",
            "{}",
            observed_at + 100,
            1.2,
            10.5 if first_10x_at else 5.2 if first_5x_at else 2.2,
            0.05 if first_90pct_loss_at else 0.4 if first_50pct_loss_at else 0.9,
            1.1,
            0.10,
            observed_at + 300,
            1.2,
            0.20,
            observed_at + 900,
            1.3,
            0.30,
            observed_at + 1800,
            1.4,
            0.40,
            observed_at + 3600,
            completed_at,
            1.5,
            0.50,
            observed_at + 21600,
            1.0,
            -0.2,
            1.6,
            0.60,
            observed_at + 86400,
            1.5,
            -0.5,
            0.2,
            -0.1,
            0.3,
            -0.2,
            0.4,
            -0.3,
            0.5,
            -0.4,
            decision_id,
            promoted_at,
            first_2x_at,
            first_5x_at,
            first_10x_at,
            first_50pct_loss_at,
            first_90pct_loss_at,
        ),
    )


def test_observer_excludes_all_pre_activation_facts(tmp_path):
    path = tmp_path / "paper.db"
    db = _db(path)

    _insert_trade(
        db,
        trade_id=1,
        created_at="2026-08-25T12:40:00+00:00",
        token="0xold",
        symbol="OLD",
        pnl=-90.0,
    )
    _insert_trade(
        db,
        trade_id=2,
        created_at="2026-08-25T12:53:00+00:00",
        token="0xnew",
        symbol="NEW",
        pnl=12.0,
    )

    _insert_decision(
        db,
        decision_id=1,
        token="0xold",
        pool="0xoldpool",
        at=SINCE_EPOCH - 60,
        action="REJECT",
        reason="OLD_REASON",
    )
    _insert_cf(
        db,
        cf_id=1,
        decision_id=1,
        token="0xold",
        pool="0xoldpool",
        observed_at=SINCE_EPOCH - 60,
        first_10x_at=SINCE_EPOCH + 10,
    )

    _insert_decision(
        db,
        decision_id=2,
        token="0xnew",
        pool="0xnewpool",
        at=SINCE_EPOCH + 60,
        action="REJECT",
        reason="NEW_REASON",
    )
    _insert_cf(
        db,
        cf_id=2,
        decision_id=2,
        token="0xnew",
        pool="0xnewpool",
        observed_at=SINCE_EPOCH + 60,
        first_2x_at=SINCE_EPOCH + 120,
    )

    db.commit()
    db.close()

    report = RuntimePerformanceObserver(
        since=SINCE,
        paper_db_path=path,
    ).build_report()

    assert report["summary"]["trades"] == 1
    assert report["summary"]["wins"] == 1
    assert report["summary"]["losses"] == 0
    assert report["summary"]["net_pnl_usdt"] == 12.0
    assert report["summary"]["decision_transitions"] == 1
    assert report["summary"]["counterfactual_observations"] == 1
    assert report["summary"]["missed_2x"] == 1
    assert report["summary"]["missed_10x"] == 0
    assert "OLD_REASON" not in report["decision_reason_counts"]
    assert report["decision_reason_counts"]["NEW_REASON"] == 1


def test_reject_can_promote_later_and_post_promotion_move_is_not_missed(
    tmp_path,
):
    path = tmp_path / "paper.db"
    db = _db(path)

    reject_at = SINCE_EPOCH + 60
    promote_at = reject_at + 18 * 3600

    _insert_decision(
        db,
        decision_id=10,
        token="bsc_0xabc",
        pool="0xpoolabc",
        at=reject_at,
        action="REJECT",
        reason="PARTICIPATION_EVIDENCE_UNKNOWN",
        context='{"plan_blockers":["VUR_KAC_ENTRY_NOT_READY"]}',
    )
    _insert_decision(
        db,
        decision_id=11,
        token="0xabc",
        pool="0xpoolabc",
        at=promote_at,
        action="PAPER_BUY",
        reason="PAPER_TRADE_OPENED",
        promotion=1,
    )

    _insert_cf(
        db,
        cf_id=10,
        decision_id=10,
        token="0xabc",
        pool="0xpoolabc",
        observed_at=reject_at,
        promoted_at=promote_at,
        first_2x_at=reject_at + 2 * 3600,
        first_5x_at=promote_at + 60,
        first_10x_at=promote_at + 120,
        completed_at=reject_at + 24 * 3600,
    )

    db.commit()
    db.close()

    report = RuntimePerformanceObserver(
        since=SINCE,
        paper_db_path=path,
    ).build_report()

    summary = report["summary"]
    assert summary["promotions_from_new_period_non_entry"] == 1
    assert summary["missed_2x"] == 1
    assert summary["missed_5x"] == 0
    assert summary["missed_10x"] == 0

    promotion = report["promotion_transitions"][0]
    assert promotion["token"] == "0xabc"
    assert promotion["from_action"] == "REJECT"
    assert promotion["hours_to_promotion"] == 18.0

    detail = report["counterfactuals"][0]
    assert detail["missed_2x"] is True
    assert detail["missed_5x"] is False
    assert detail["missed_10x"] is False
    assert "PARTICIPATION_EVIDENCE_UNKNOWN" in detail["reasons"]
    assert "VUR_KAC_ENTRY_NOT_READY" in detail["reasons"]


def test_prevented_collapse_and_reason_scorecard_are_separate_from_missed_move(
    tmp_path,
):
    path = tmp_path / "paper.db"
    db = _db(path)

    at = SINCE_EPOCH + 120

    _insert_decision(
        db,
        decision_id=20,
        token="0xrug",
        pool="0xrugpool",
        at=at,
        action="REJECT",
        reason="PARTICIPATION_CONCENTRATED",
        context='{"plan_blockers":["SUSPICIOUS_VOLUME"]}',
    )
    _insert_cf(
        db,
        cf_id=20,
        decision_id=20,
        token="0xrug",
        pool="0xrugpool",
        observed_at=at,
        first_50pct_loss_at=at + 300,
        first_90pct_loss_at=at + 600,
        completed_at=at + 86400,
    )

    db.commit()
    db.close()

    report = RuntimePerformanceObserver(
        since=SINCE,
        paper_db_path=path,
    ).build_report()

    summary = report["summary"]
    assert summary["missed_2x"] == 0
    assert summary["prevented_50pct_loss"] == 1
    assert summary["prevented_90pct_loss"] == 1

    concentrated = report["reason_scorecards"][
        "PARTICIPATION_CONCENTRATED"
    ]
    suspicious = report["reason_scorecards"]["SUSPICIOUS_VOLUME"]

    assert concentrated["observations"] == 1
    assert concentrated["prevented_90pct_loss"] == 1
    assert suspicious["observations"] == 1
    assert suspicious["prevented_50pct_loss"] == 1


def test_observer_opens_database_query_only(tmp_path):
    path = tmp_path / "paper.db"
    db = _db(path)
    db.commit()
    db.close()

    observer = RuntimePerformanceObserver(
        since=SINCE,
        paper_db_path=path,
    )

    ro = observer._open()
    try:
        assert ro.execute("PRAGMA query_only;").fetchone()[0] == 1
        try:
            ro.execute(
                "INSERT INTO paper_trades(id) VALUES(999)"
            )
        except sqlite3.OperationalError:
            pass
        else:
            raise AssertionError("observer connection accepted a write")
    finally:
        ro.close()
