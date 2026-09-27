"""Eligibility for calibration; never rewrites historical economics or proof."""
import json
import math
from datetime import datetime

from app.config.contracts import USDT

CURRENT_PAPER_MODEL = "corrected_paper_v1"


def _object(raw):
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _address(value):
    return str(value or "").lower()


def _positive(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value > 0)


def _execution(evidence, side, row):
    proof = _object(_object(evidence).get(side.lower()))
    block = _object(proof.get("block"))
    delta_name = "received_token_raw" if side == "BUY" else "received_quote_raw"
    delta = proof.get(delta_name)
    block_hash = block.get("hash")
    valid_hash = (isinstance(block_hash, str) and len(block_hash) == 66
                  and block_hash.startswith("0x")
                  and all(c in "0123456789abcdefABCDEF" for c in block_hash[2:]))
    return bool(
        proof.get("contract") == "phase15h_transaction_simulation_v1"
        and proof.get("side") == side and proof.get("status") == "SUCCESS"
        and proof.get("fill_status") == "SIMULATED_RECIPIENT_DELTA"
        and _address(proof.get("token")) == _address(row["token"])
        and _address(proof.get("pool")) == _address(row["pool"])
        and _address(proof.get("quote_token")) == USDT.lower()
        and block.get("chain_id") == 56
        and type(block.get("number")) is int and block["number"] >= 0
        and valid_hash and type(delta) is int and delta > 0
        and proof.get("recipient_balance_delta_raw") == delta
        and (side == "BUY" or proof.get("paper_position_id") == row["position_id"])
    )


def current_model_outcome(db, row, active_run):
    """Require the corrected admission contract and durable USDT execution.

    Freshness is evaluated at admission time, not the time of calibration.
    A new run also fences off all earlier samples, without deleting them.
    """
    try:
        return _current_model_outcome(db, row, active_run)
    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
        return False


def _current_model_outcome(db, row, active_run):
    if active_run and (row["paper_run_id"] != active_run["id"]
                       or row["position_id"] <= active_run["start_trade_id"]):
        return False
    if not row["token"] or not row["pool"] or not _positive(row["entry_price"]):
        return False
    context = _object(row["opening_context_json"])
    admission = _object(context.get("admission_provenance"))
    integrity = _object(admission.get("price_integrity"))
    observation = _object(context.get("price_observation"))
    if (admission.get("contract") != CURRENT_PAPER_MODEL
            or integrity.get("state") not in {"VERIFIED_NORMAL", "VERIFIED_EXTREME"}
            or _address(observation.get("pool")) != _address(row["pool"])
            or _address(observation.get("base_token") or observation.get("token")) != _address(row["token"])
            or _address(observation.get("quote_token")) != USDT.lower()
            or observation.get("chain") != "bsc"
            or str(observation.get("dex", "")).replace("-", "_").lower() != "pancakeswap_v2"
            or observation.get("source") not in {"geckoterminal", "dexscreener", "pancakeswap_v2_sync"}):
        return False
    try:
        verified = datetime.fromisoformat(admission["verified_at"])
        observed = datetime.fromisoformat(observation["observed_at"])
        if (verified.utcoffset() is None or observed.utcoffset() is None
                or not 0 <= (verified - observed).total_seconds() <= 30
                or float(integrity["price"]) != float(row["entry_price"])
                or float(observation["price_usd"]) != float(row["entry_price"])):
            return False
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    if not (_execution(context.get("phase15h_execution"), "BUY", row)
            and _execution(row["closing_execution_json"], "SELL", row)):
        return False
    closing = _object(_object(row["closing_execution_json"]).get("sell"))
    if closing.get("paper_exit_fraction") != 1.0 or not closing.get("exit_stage"):
        return False
    columns = {item[1] for item in db.execute("PRAGMA table_info(paper_realizations)")}
    if not columns:
        return not (row["tp1_done"] or row["tp2_done"])
    partials = db.execute("SELECT * FROM paper_realizations WHERE position_id=?",
                          (row["position_id"],)).fetchall()
    stages = set()
    for partial in partials:
        if "execution_evidence_json" not in columns:
            return False
        evidence = partial["execution_evidence_json"]
        sell = _object(_object(evidence).get("sell"))
        fraction = sell.get("paper_exit_fraction")
        if (not _execution(evidence, "SELL", row) or not _positive(fraction)
                or fraction >= 1 or fraction != partial["close_fraction"]
                or sell.get("exit_stage") != "NORMAL_" + partial["stage"]):
            return False
        stages.add(partial["stage"])
    return not ((row["tp1_done"] and "TP1" not in stages)
                or (row["tp2_done"] and "TP2" not in stages))
