import sqlite3
from pathlib import Path

DB = Path("data/paper_trades.db")

class PaperDatabase:

    def __init__(self):
        DB.parent.mkdir(exist_ok=True)

        self.conn = sqlite3.connect(DB)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            created_at TEXT,

            token TEXT,

            symbol TEXT,

            entry_price REAL,

            exit_price REAL,

            amount_bnb REAL,

            gross_pnl REAL,

            net_pnl REAL,

            gas_buy REAL,

            gas_sell REAL,

            swap_fee REAL,

            buy_tax REAL,

            sell_tax REAL,

            slippage REAL,

            mev REAL,

            status TEXT

        )
        """)

        self.conn.commit()

    def insert(self,data):

        self.conn.execute("""

        INSERT INTO paper_trades(

        created_at,
        token,
        symbol,
        entry_price,
        exit_price,
        amount_bnb,
        gross_pnl,
        net_pnl,
        gas_buy,
        gas_sell,
        swap_fee,
        buy_tax,
        sell_tax,
        slippage,
        mev,
        status

        )

        VALUES(

        :created_at,
        :token,
        :symbol,
        :entry_price,
        :exit_price,
        :amount_bnb,
        :gross_pnl,
        :net_pnl,
        :gas_buy,
        :gas_sell,
        :swap_fee,
        :buy_tax,
        :sell_tax,
        :slippage,
        :mev,
        :status

        )

        """,data)

        self.conn.commit()
