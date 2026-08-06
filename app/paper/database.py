import sqlite3
from pathlib import Path
from datetime import datetime, UTC

DB = Path("data/paper_trades.db")


class PaperDatabase:

    def __init__(self):

        DB.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(DB)
        self.conn.row_factory = sqlite3.Row

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            created_at TEXT,

            closed_at TEXT,

            token TEXT,

            symbol TEXT,

            entry_price REAL,

            current_price REAL,

            exit_price REAL,

            highest_price REAL,

            lowest_price REAL,

            tp_price REAL,

            sl_price REAL,

            amount_bnb REAL,

            token_amount REAL,

            gross_pnl REAL,

            net_pnl REAL,

            roi REAL,

            gas_buy REAL,

            gas_sell REAL,

            swap_fee REAL,

            buy_tax REAL,

            sell_tax REAL,

            slippage REAL,

            mev REAL,

            close_reason TEXT,

            status TEXT

        )
        """)

        self.conn.commit()

    def insert(self, data):

        row = {

            "created_at": datetime.now(UTC).isoformat(),
            "closed_at": None,

            "token": "",
            "symbol": "",

            "entry_price": 0.0,
            "current_price": 0.0,
            "exit_price": 0.0,

            "highest_price": 0.0,
            "lowest_price": 0.0,

            "tp_price": 0.0,
            "sl_price": 0.0,

            "amount_bnb": 0.0,
            "token_amount": 0.0,

            "gross_pnl": 0.0,
            "net_pnl": 0.0,
            "roi": 0.0,

            "gas_buy": 0.0,
            "gas_sell": 0.0,
            "swap_fee": 0.0,

            "buy_tax": 0.0,
            "sell_tax": 0.0,

            "slippage": 0.0,
            "mev": 0.0,

            "close_reason": "",
            "status": "OPEN"

        }

        row.update(data)

        if "amount" in row and "amount_bnb" not in data:
            row["amount_bnb"] = row["amount"]

        if "mev_risk" in row and "mev" not in data:
            row["mev"] = row["mev_risk"]

        if row["highest_price"] == 0:
            row["highest_price"] = row["entry_price"]

        if row["lowest_price"] == 0:
            row["lowest_price"] = row["entry_price"]

        self.conn.execute("""

        INSERT INTO paper_trades(

            created_at,
            closed_at,
            token,
            symbol,
            entry_price,
            current_price,
            exit_price,
            highest_price,
            lowest_price,
            tp_price,
            sl_price,
            amount_bnb,
            token_amount,
            gross_pnl,
            net_pnl,
            roi,
            gas_buy,
            gas_sell,
            swap_fee,
            buy_tax,
            sell_tax,
            slippage,
            mev,
            close_reason,
            status

        )

        VALUES(

            :created_at,
            :closed_at,
            :token,
            :symbol,
            :entry_price,
            :current_price,
            :exit_price,
            :highest_price,
            :lowest_price,
            :tp_price,
            :sl_price,
            :amount_bnb,
            :token_amount,
            :gross_pnl,
            :net_pnl,
            :roi,
            :gas_buy,
            :gas_sell,
            :swap_fee,
            :buy_tax,
            :sell_tax,
            :slippage,
            :mev,
            :close_reason,
            :status

        )

        """, row)

        self.conn.commit()

    def open_positions(self):

        cur = self.conn.execute("""

        SELECT *

        FROM paper_trades

        WHERE status='OPEN'

        ORDER BY id

        """)

        return [dict(r) for r in cur.fetchall()]


    def update_position(self, trade_id, **fields):

        if not fields:
            return

        sql = ", ".join(f"{k}=:{k}" for k in fields)
        fields["id"] = trade_id

        self.conn.execute(
            f"UPDATE paper_trades SET {sql} WHERE id=:id",
            fields
        )

        self.conn.commit()

    def close_position(
        self,
        trade_id,
        exit_price,
        gross_pnl,
        net_pnl,
        roi,
        reason
    ):

        self.conn.execute("""

        UPDATE paper_trades

        SET

            exit_price=?,
            current_price=?,
            gross_pnl=?,
            net_pnl=?,
            roi=?,
            status='CLOSED',
            close_reason=?,
            closed_at=?

        WHERE id=?

        """,(
            exit_price,
            exit_price,
            gross_pnl,
            net_pnl,
            roi,
            reason,
            datetime.now(UTC).isoformat(),
            trade_id
        ))

        self.conn.commit()


    def has_open_position(self, token):

        row = self.conn.execute(

            """
            SELECT 1
            FROM paper_trades
            WHERE token=?
              AND status='OPEN'
            LIMIT 1
            """,

            (token,)

        ).fetchone()

        return row is not None
