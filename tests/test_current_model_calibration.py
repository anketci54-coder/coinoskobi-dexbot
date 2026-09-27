import json
import sqlite3

import pytest

from app.paper.calibration_provenance import current_model_open_position
from app.paper.schema import ensure_paper_schema
from app.risk.paper_position_sizing import _empirical_outcome_calibration
from tests.paper_calibration_fixtures import opening, execution, stamp_current_model


def test_legacy_economics_are_preserved_but_cannot_calibrate(tmp_path):
    path = tmp_path / "paper.db"
    with sqlite3.connect(path) as db:
        ensure_paper_schema(db)
        db.execute("""INSERT INTO paper_trades (
            status, created_at, closed_at, entry_price, exit_price,
            entry_amount_usdt, gross_pnl_usdt, net_pnl_usdt,
            mathematical_plan_json, math_state_json
        ) VALUES ('CLOSED', '2026-09-20T00:00:00+00:00',
                  '2026-09-20T01:00:00+00:00', 1, .8, 100, -20, -22, ?, '{}')""",
                   (json.dumps({"capital": {"available_usdt": 10000},
                                "entry": {"band_low": .9}}),))
    result = _empirical_outcome_calibration(path)
    assert result["gap_samples"] == 0
    assert result["account_risk_samples"] == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*), sum(net_pnl_usdt) FROM paper_trades").fetchone() == (1, -22)


def _current_db(path):
    db = sqlite3.connect(path)
    ensure_paper_schema(db)
    db.execute("""INSERT INTO paper_trades (
        status, created_at, closed_at, entry_price, exit_price,
        entry_amount_usdt, gross_pnl_usdt, net_pnl_usdt,
        mathematical_plan_json, math_state_json
    ) VALUES ('CLOSED', '2026-09-27T10:00:00+00:00',
              '2026-09-27T11:00:00+00:00', 1, .8, 100, -20, -22, ?, '{}')""",
               (json.dumps({"capital": {"available_usdt": 10000},
                            "entry": {"band_low": .9}}),))
    stamp_current_model(db)
    db.commit()
    return db


def test_current_proven_outcome_calibrates(tmp_path):
    path = tmp_path / "paper.db"
    _current_db(path).close()
    result = _empirical_outcome_calibration(path)
    assert result["ready"] is True
    assert result["gap_multiplier"] == pytest.approx(2)
    assert result["account_risk_budget_fraction"] == pytest.approx(.0022)
    assert result["cost_uncertainty_fraction"] == pytest.approx(.02)


@pytest.mark.parametrize("defect", [
    "old_model", "missing_buy", "buy_unknown", "buy_pool", "buy_quote",
    "price_stale", "price_pool", "price_unverified", "price_missing",
    "sell_missing", "sell_revert", "sell_position", "sell_chain", "sell_hash",
    "sell_delta", "sell_quote", "sell_fraction", "tp1_missing",
    "malformed_state", "malformed_source", "malformed_time",
])
def test_incomplete_or_wrong_proof_never_calibrates(tmp_path, defect):
    path = tmp_path / "paper.db"
    db = _current_db(path)
    context, close = opening(), execution("SELL")
    if defect == "malformed_state":
        context["admission_provenance"]["price_integrity"]["state"] = []
    elif defect == "malformed_source":
        context["price_observation"]["source"] = {}
    elif defect == "malformed_time":
        context["admission_provenance"]["verified_at"] = 5
    elif defect == "old_model":
        context["admission_provenance"]["contract"] = "legacy"
    elif defect == "missing_buy":
        context.pop("phase15h_execution")
    elif defect.startswith("buy_"):
        key, value = {"buy_unknown": ("status", "UNKNOWN"),
                      "buy_pool": ("pool", "wrong"), "buy_quote": ("quote_token", "WBNB")}[defect]
        context["phase15h_execution"]["buy"][key] = value
    elif defect == "price_stale":
        context["price_observation"]["observed_at"] = "2026-09-27T09:59:00+00:00"
    elif defect == "price_pool":
        context["price_observation"]["pool"] = "wrong"
    elif defect == "price_missing":
        context.pop("price_observation")
    elif defect == "price_unverified":
        context["admission_provenance"]["price_integrity"]["state"] = "PRICE_UNVERIFIED"
    elif defect == "sell_missing":
        close = {}
    elif defect in {"sell_chain", "sell_hash"}:
        close["sell"]["block"]["chain_id" if defect == "sell_chain" else "hash"] = 1
    elif defect.startswith("sell_"):
        key, value = {"sell_revert": ("status", "REVERT"), "sell_position": ("paper_position_id", 2),
                      "sell_delta": ("recipient_balance_delta_raw", 0),
                      "sell_quote": ("quote_token", "WBNB"), "sell_fraction": ("paper_exit_fraction", .5)}[defect]
        close["sell"][key] = value
    else:
        db.execute("UPDATE paper_trades SET tp1_done=1")
    db.execute("UPDATE paper_trades SET opening_context_json=?, closing_execution_json=?",
               (json.dumps(context), json.dumps(close)))
    db.commit()
    before = db.execute("SELECT * FROM paper_trades").fetchall()
    result = _empirical_outcome_calibration(path)
    assert result["gap_samples"] == result["cost_samples"] == result["account_risk_samples"] == 0
    assert result["unproven_samples"] == 1
    assert db.execute("SELECT * FROM paper_trades").fetchall() == before
    db.close()


def test_every_partial_sell_requires_durable_bound_proof(tmp_path):
    path = tmp_path / "paper.db"
    db = _current_db(path)
    db.execute("UPDATE paper_trades SET tp1_done=1")
    db.execute("""INSERT INTO paper_realizations (position_id, stage, observed_at, price,
        token_amount, close_fraction, gross_proceeds_usdt, net_proceeds_usdt,
        sold_cost_basis_usdt, realized_pnl_usdt, execution_evidence_json)
        VALUES (1, 'TP1', '2026-09-27T10:30:00+00:00', 1.2, 20, .2, 24, 23, 20, 3, ?)""",
               (json.dumps(execution("SELL", stage="NORMAL_TP1", fraction=.2)),))
    db.commit()
    assert _empirical_outcome_calibration(path)["ready"] is True
    db.execute("UPDATE paper_realizations SET execution_evidence_json=NULL")
    db.commit()
    assert _empirical_outcome_calibration(path)["ready"] is False
    db.close()


def test_active_run_excludes_older_and_unattributed_outcomes(tmp_path):
    from app.paper.run_boundary import start_paper_run
    path = tmp_path / "paper.db"
    db = _current_db(path)
    run = start_paper_run(path, "new", apply=True)["run"]
    assert _empirical_outcome_calibration(path)["ready"] is False
    # Even a stamped historical row cannot cross the ID boundary.
    db.execute("UPDATE paper_trades SET paper_run_id=?", (run["id"],))
    db.commit()
    assert _empirical_outcome_calibration(path)["ready"] is False
    # A new attributed trade qualifies; a post-boundary ID alone does not.
    db.execute("UPDATE paper_trades SET id=2, paper_run_id=NULL")
    db.execute("UPDATE paper_trades SET closing_execution_json=?", (json.dumps(execution("SELL", 2)),))
    db.commit()
    assert _empirical_outcome_calibration(path)["ready"] is False
    db.execute("UPDATE paper_trades SET paper_run_id=?", (run["id"],))
    db.commit()
    assert _empirical_outcome_calibration(path)["ready"] is True
    db.close()

def test_current_model_open_position_requires_corrected_admission_and_buy_proof(tmp_path):
    path = tmp_path / "paper.db"
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    ensure_paper_schema(db)
    db.execute(
        """INSERT INTO paper_trades (
            token, pool, status, entry_price, opening_context_json
        ) VALUES (?, ?, 'OPEN', 1, ?)""",
        (
            "0x" + "12" * 20,
            "0x" + "34" * 20,
            json.dumps(opening(1.0)),
        ),
    )
    row = db.execute(
        """SELECT id AS position_id, token, pool, entry_price,
                  opening_context_json, paper_run_id
           FROM paper_trades"""
    ).fetchone()
    assert current_model_open_position(row) is True
    context = json.loads(row["opening_context_json"])
    context["phase15h_execution"]["buy"]["status"] = "UNKNOWN"
    db.execute(
        "UPDATE paper_trades SET opening_context_json=?",
        (json.dumps(context),),
    )
    db.commit()
    row = db.execute(
        """SELECT id AS position_id, token, pool, entry_price,
                  opening_context_json, paper_run_id
           FROM paper_trades"""
    ).fetchone()
    assert current_model_open_position(row) is False
    db.close()
