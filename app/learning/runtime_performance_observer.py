import argparse
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_PAPER_DB = "data/paper_trades.db"
HORIZON_LABELS = ("5m", "15m", "30m", "60m", "6h", "24h")


def _number(value):
    try:
        if value is None:
            return None
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _json_dict(raw):
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _utc_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError("timestamp is required")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _timestamp(value):
    try:
        return _utc_datetime(value).timestamp()
    except (TypeError, ValueError):
        return None


def _canonical(value):
    value = str(value or "").strip().lower()
    if value.startswith("bsc_"):
        value = value[4:]
    return value


def _event_before_promotion(event_at, promoted_at):
    event_at = _number(event_at)
    promoted_at = _number(promoted_at)

    if event_at is None:
        return False

    return promoted_at is None or event_at < promoted_at


def _return_pct(value):
    value = _number(value)
    return None if value is None else value * 100.0


def _trade_excursion(entry_price, high_price, low_price):
    entry = _number(entry_price)
    high = _number(high_price)
    low = _number(low_price)

    if entry is None or entry <= 0:
        return None, None

    mfe = (
        high / entry - 1.0
        if high is not None and high > 0
        else None
    )
    mae = (
        low / entry - 1.0
        if low is not None and low > 0
        else None
    )
    return mfe, mae


def _decision_reasons(row):
    reasons = []

    reason = str(row.get("reason") or "").strip()
    if reason:
        reasons.append(reason)

    context = _json_dict(row.get("context_json"))

    for key in ("plan_blockers", "sizing_blockers"):
        values = context.get(key) or []
        if isinstance(values, (list, tuple)):
            reasons.extend(
                str(value).strip()
                for value in values
                if str(value).strip()
            )

    context_reason = str(context.get("reason") or "").strip()
    if context_reason:
        reasons.append(context_reason)

    return tuple(dict.fromkeys(reasons)) or ("UNSPECIFIED",)


class RuntimePerformanceObserver:
    """
    Read-only post-activation performance observer.

    It intentionally has no decision, paper, live, wallet, signing or
    execution authority and performs no provider calls.  The observer only
    reads durable PAPER trade, candidate-decision and counterfactual outcome
    facts written by the running system.
    """

    def __init__(
        self,
        *,
        since,
        paper_db_path=DEFAULT_PAPER_DB,
    ):
        self.since = _utc_datetime(since)
        self.since_epoch = self.since.timestamp()
        self.paper_db_path = str(paper_db_path)

    def _open(self):
        path = Path(self.paper_db_path)
        if not path.exists():
            raise FileNotFoundError(self.paper_db_path)

        db = sqlite3.connect(
            f"file:{path}?mode=ro",
            uri=True,
            timeout=5,
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON;")
        return db

    @staticmethod
    def _table_exists(db, table_name):
        return (
            db.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type='table' AND name=?
                """,
                (table_name,),
            ).fetchone()
            is not None
        )

    def _new_trades(self, db):
        if not self._table_exists(db, "paper_trades"):
            return []

        rows = db.execute(
            """
            SELECT
                id,
                created_at,
                closed_at,
                token,
                symbol,
                pool,
                dex,
                status,
                trade_policy,
                entry_price,
                current_price,
                exit_price,
                highest_price,
                lowest_price,
                entry_amount_usdt,
                risk_amount_usdt,
                position_size_pct,
                sizing_reason,
                gross_pnl_usdt,
                net_pnl_usdt,
                roi,
                close_reason,
                tp1_done,
                tp2_done,
                runner_active
            FROM paper_trades
            ORDER BY id
            """
        ).fetchall()

        result = []

        for raw in rows:
            row = dict(raw)
            created_epoch = _timestamp(row.get("created_at"))
            if (
                created_epoch is None
                or created_epoch < self.since_epoch
            ):
                continue

            entry = _number(row.get("entry_amount_usdt"))
            risk = _number(row.get("risk_amount_usdt"))
            mfe, mae = _trade_excursion(
                row.get("entry_price"),
                row.get("highest_price"),
                row.get("lowest_price"),
            )

            row["risk_entry_fraction"] = (
                risk / entry
                if entry is not None and entry > 0 and risk is not None
                else None
            )
            row["mfe"] = mfe
            row["mae"] = mae
            result.append(row)

        return result

    def _new_decisions(self, db):
        if not self._table_exists(db, "candidate_decision_history"):
            return []

        rows = db.execute(
            """
            SELECT
                id,
                token,
                pool,
                observed_at,
                decision_action,
                reason,
                signal_state,
                entry_price,
                context_json,
                promotion
            FROM candidate_decision_history
            WHERE observed_at >= ?
            ORDER BY observed_at, id
            """,
            (self.since_epoch,),
        ).fetchall()

        return [dict(row) for row in rows]

    def _new_counterfactuals(self, db):
        if not self._table_exists(db, "counterfactual_observations"):
            return []

        rows = db.execute(
            """
            SELECT *
            FROM counterfactual_observations
            WHERE observed_at >= ?
            ORDER BY observed_at, id
            """,
            (self.since_epoch,),
        ).fetchall()

        return [dict(row) for row in rows]

    @staticmethod
    def _promotion_transitions(decisions):
        history = defaultdict(list)
        promotions = []

        for row in decisions:
            key = (
                _canonical(row.get("token")),
                _canonical(row.get("pool")),
            )
            history[key].append(row)

            if not int(row.get("promotion") or 0):
                continue

            previous = None
            for candidate in reversed(history[key][:-1]):
                action = str(
                    candidate.get("decision_action") or ""
                ).upper()
                if action != "PAPER_BUY":
                    previous = candidate
                    break

            if previous is None:
                continue

            promoted_at = _number(row.get("observed_at"))
            previous_at = _number(previous.get("observed_at"))

            promotions.append(
                {
                    "token": key[0],
                    "pool": key[1],
                    "from_action": previous.get("decision_action"),
                    "from_reason": previous.get("reason"),
                    "from_signal_state": previous.get("signal_state"),
                    "from_observed_at": previous_at,
                    "promoted_at": promoted_at,
                    "hours_to_promotion": (
                        (promoted_at - previous_at) / 3600.0
                        if promoted_at is not None
                        and previous_at is not None
                        and promoted_at >= previous_at
                        else None
                    ),
                }
            )

        return promotions

    @staticmethod
    def _counterfactual_detail(row, decision_by_id):
        decision = decision_by_id.get(row.get("decision_history_id"))
        promoted_at = _number(row.get("promoted_at"))

        detail = {
            "id": row.get("id"),
            "decision_history_id": row.get("decision_history_id"),
            "token": _canonical(row.get("token")),
            "pool": _canonical(row.get("pool")),
            "observed_at": _number(row.get("observed_at")),
            "entry_price": _number(row.get("entry_price")),
            "candidate_action": row.get("candidate_action"),
            "signal_state": row.get("signal_state"),
            "reason": decision.get("reason") if decision else None,
            "reasons": list(_decision_reasons(decision or {})),
            "promoted_at": promoted_at,
            "completed_at": _number(row.get("completed_at")),
            "last_observed_at": _number(row.get("last_observed_at")),
            "last_price": _number(row.get("last_price")),
        }

        entry = _number(row.get("entry_price"))
        maximum = _number(row.get("max_price"))
        minimum = _number(row.get("min_price"))

        detail["max_return"] = (
            maximum / entry - 1.0
            if entry is not None and entry > 0 and maximum is not None
            else None
        )
        detail["min_return"] = (
            minimum / entry - 1.0
            if entry is not None and entry > 0 and minimum is not None
            else None
        )

        for label in HORIZON_LABELS:
            detail[f"return_{label}"] = _number(
                row.get(f"return_{label}")
            )
            detail[f"mfe_{label}"] = _number(
                row.get(f"mfe_{label}")
            )
            detail[f"mae_{label}"] = _number(
                row.get(f"mae_{label}")
            )

        for label in ("2x", "5x", "10x"):
            event_at = _number(row.get(f"first_{label}_at"))
            detail[f"first_{label}_at"] = event_at
            detail[f"missed_{label}"] = _event_before_promotion(
                event_at,
                promoted_at,
            )

        for label in ("50pct_loss", "90pct_loss"):
            event_at = _number(row.get(f"first_{label}_at"))
            detail[f"first_{label}_at"] = event_at
            detail[f"prevented_{label}"] = _event_before_promotion(
                event_at,
                promoted_at,
            )

        return detail

    @staticmethod
    def _scorecard(details):
        cards = defaultdict(
            lambda: {
                "observations": 0,
                "pending": 0,
                "promoted": 0,
                "missed_2x": 0,
                "missed_5x": 0,
                "missed_10x": 0,
                "prevented_50pct_loss": 0,
                "prevented_90pct_loss": 0,
                "returns": defaultdict(list),
                "mfe": defaultdict(list),
                "mae": defaultdict(list),
            }
        )

        for row in details:
            for reason in row.get("reasons") or ["UNSPECIFIED"]:
                card = cards[reason]
                card["observations"] += 1
                card["pending"] += int(row.get("completed_at") is None)
                card["promoted"] += int(row.get("promoted_at") is not None)

                for label in ("2x", "5x", "10x"):
                    card[f"missed_{label}"] += int(
                        bool(row.get(f"missed_{label}"))
                    )

                for label in ("50pct_loss", "90pct_loss"):
                    card[f"prevented_{label}"] += int(
                        bool(row.get(f"prevented_{label}"))
                    )

                for label in HORIZON_LABELS:
                    for source, target in (
                        ("return", "returns"),
                        ("mfe", "mfe"),
                        ("mae", "mae"),
                    ):
                        value = _number(row.get(f"{source}_{label}"))
                        if value is not None:
                            card[target][label].append(value)

        result = {}

        for reason, card in cards.items():
            item = {
                key: value
                for key, value in card.items()
                if key not in {"returns", "mfe", "mae"}
            }

            for source in ("returns", "mfe", "mae"):
                for label, values in card[source].items():
                    item[f"avg_{source[:-1] if source.endswith('s') else source}_{label}"] = (
                        sum(values) / len(values)
                    )

            result[reason] = item

        return dict(
            sorted(
                result.items(),
                key=lambda item: (
                    -item[1]["observations"],
                    item[0],
                ),
            )
        )

    def build_report(self, *, detail_limit=100):
        db = self._open()

        try:
            trades = self._new_trades(db)
            decisions = self._new_decisions(db)
            counterfactuals = self._new_counterfactuals(db)
        finally:
            db.close()

        decision_by_id = {
            int(row["id"]): row
            for row in decisions
        }

        details = [
            self._counterfactual_detail(row, decision_by_id)
            for row in counterfactuals
        ]

        closed = [
            row for row in trades
            if str(row.get("status") or "").upper() == "CLOSED"
        ]
        wins = [
            row for row in closed
            if (_number(row.get("net_pnl_usdt")) or 0.0) > 0
        ]
        losses = [
            row for row in closed
            if (_number(row.get("net_pnl_usdt")) or 0.0) < 0
        ]

        action_counts = Counter(
            str(row.get("decision_action") or "UNKNOWN").upper()
            for row in decisions
        )
        reason_counts = Counter()
        for row in decisions:
            for reason in _decision_reasons(row):
                reason_counts[reason] += 1

        promotions = self._promotion_transitions(decisions)

        summary = {
            "trades": len(trades),
            "open_trades": sum(
                1
                for row in trades
                if str(row.get("status") or "").upper() == "OPEN"
            ),
            "closed_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (
                len(wins) / len(closed)
                if closed
                else None
            ),
            "net_pnl_usdt": sum(
                _number(row.get("net_pnl_usdt")) or 0.0
                for row in closed
            ),
            "decision_transitions": len(decisions),
            "distinct_candidate_pools": len(
                {
                    (
                        _canonical(row.get("token")),
                        _canonical(row.get("pool")),
                    )
                    for row in decisions
                }
            ),
            "counterfactual_observations": len(details),
            "counterfactual_pending": sum(
                1 for row in details if row.get("completed_at") is None
            ),
            "promotions_from_new_period_non_entry": len(promotions),
            "missed_2x": sum(bool(row.get("missed_2x")) for row in details),
            "missed_5x": sum(bool(row.get("missed_5x")) for row in details),
            "missed_10x": sum(bool(row.get("missed_10x")) for row in details),
            "prevented_50pct_loss": sum(
                bool(row.get("prevented_50pct_loss")) for row in details
            ),
            "prevented_90pct_loss": sum(
                bool(row.get("prevented_90pct_loss")) for row in details
            ),
        }

        return {
            "state": "READY",
            "scope": "POST_ACTIVATION_READ_ONLY",
            "since_utc": self.since.isoformat(),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "paper_db_path": self.paper_db_path,
            "read_only": True,
            "provider_calls": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
            "summary": summary,
            "decision_action_counts": dict(action_counts),
            "decision_reason_counts": dict(reason_counts.most_common()),
            "reason_scorecards": self._scorecard(details),
            "promotion_transitions": promotions[-detail_limit:],
            "trades": trades[-detail_limit:],
            "counterfactuals": details[-detail_limit:],
        }


def format_report(report):
    summary = report["summary"]

    lines = [
        "===== COINOSKOBI NEW-RUNTIME PERFORMANCE =====",
        f"SINCE_UTC={report['since_utc']}",
        "READ_ONLY=true",
        (
            "TRADES="
            f"{summary['trades']} "
            f"OPEN={summary['open_trades']} "
            f"CLOSED={summary['closed_trades']} "
            f"WINS={summary['wins']} "
            f"LOSSES={summary['losses']} "
            f"NET_PNL_USDT={summary['net_pnl_usdt']:.6f}"
        ),
        (
            "DECISIONS="
            f"{summary['decision_transitions']} "
            f"POOLS={summary['distinct_candidate_pools']} "
            f"COUNTERFACTUALS={summary['counterfactual_observations']} "
            f"PENDING={summary['counterfactual_pending']}"
        ),
        (
            "PROMOTIONS_FROM_NEW_PERIOD_NON_ENTRY="
            f"{summary['promotions_from_new_period_non_entry']}"
        ),
        (
            "MISSED="
            f"2X:{summary['missed_2x']} "
            f"5X:{summary['missed_5x']} "
            f"10X:{summary['missed_10x']}"
        ),
        (
            "PREVENTED="
            f"LOSS50:{summary['prevented_50pct_loss']} "
            f"LOSS90:{summary['prevented_90pct_loss']}"
        ),
        "",
        "--- DECISION ACTIONS ---",
    ]

    for action, count in report["decision_action_counts"].items():
        lines.append(f"{action}={count}")

    lines.extend(["", "--- TOP REASONS ---"])
    for reason, count in list(report["decision_reason_counts"].items())[:20]:
        lines.append(f"{reason}={count}")

    lines.extend(["", "--- NEW TRADES ---"])
    for row in report["trades"]:
        lines.append(
            "ID={id} SYMBOL={symbol} STATUS={status} "
            "PNL={pnl} ROI={roi} MFE={mfe} MAE={mae} "
            "CLOSE={close}".format(
                id=row.get("id"),
                symbol=row.get("symbol"),
                status=row.get("status"),
                pnl=row.get("net_pnl_usdt"),
                roi=_return_pct(row.get("roi")),
                mfe=_return_pct(row.get("mfe")),
                mae=_return_pct(row.get("mae")),
                close=row.get("close_reason"),
            )
        )

    lines.extend(["", "--- PROMOTIONS ---"])
    for row in report["promotion_transitions"]:
        lines.append(
            "TOKEN={token} FROM={from_action} REASON={reason} "
            "HOURS={hours}".format(
                token=row.get("token"),
                from_action=row.get("from_action"),
                reason=row.get("from_reason"),
                hours=row.get("hours_to_promotion"),
            )
        )

    lines.extend(["", "--- COUNTERFACTUAL FLAGS ---"])
    for row in report["counterfactuals"]:
        flags = []
        for name in (
            "missed_2x",
            "missed_5x",
            "missed_10x",
            "prevented_50pct_loss",
            "prevented_90pct_loss",
        ):
            if row.get(name):
                flags.append(name.upper())

        if flags:
            lines.append(
                f"TOKEN={row.get('token')} "
                f"REASON={row.get('reason')} "
                f"FLAGS={','.join(flags)}"
            )

    lines.append("NEW_RUNTIME_PERFORMANCE_OBSERVER=PASS")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Coinoskobi post-activation performance report"
        )
    )
    parser.add_argument("--since", required=True)
    parser.add_argument("--paper-db", default=DEFAULT_PAPER_DB)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = RuntimePerformanceObserver(
        since=args.since,
        paper_db_path=args.paper_db,
    ).build_report(
        detail_limit=max(1, args.limit)
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_report(report))


if __name__ == "__main__":
    main()
