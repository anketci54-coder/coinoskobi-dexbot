from concurrent.futures import ThreadPoolExecutor

import app.paper.database as database_module
from app.paper.database import PaperDatabase


def _reset_database():
    instance = PaperDatabase._instance

    if (
        instance is not None
        and hasattr(instance, "conn")
    ):
        try:
            instance.conn.close()
        except Exception:
            pass

    PaperDatabase._instance = None
    PaperDatabase._initialized = False


def _trade(token):
    return {
        "token": token,
        "symbol": "TEST",
        "entry_price": 1.0,
        "current_price": 1.0,
        "highest_price": 1.0,
        "lowest_price": 1.0,
        "tp_price": 1.2,
        "sl_price": 0.9,
        "amount_bnb": 0.01,
        "token_amount": 0.01,
        "gas_buy": 0.0,
        "gas_sell": 0.0,
        "swap_fee": 0.0,
        "buy_tax": 0.0,
        "sell_tax": 0.0,
        "slippage": 0.0,
        "mev": 0.0,
        "status": "OPEN",
    }


def test_atomic_same_token_only_one_open(
    tmp_path,
    monkeypatch,
):
    _reset_database()

    monkeypatch.setattr(
        database_module,
        "DB",
        tmp_path / "paper.db",
    )

    db = PaperDatabase()

    def worker(_):
        return db.insert_if_no_open_position(
            _trade("0xabc")
        )

    with ThreadPoolExecutor(
        max_workers=16
    ) as executor:
        results = list(
            executor.map(
                worker,
                range(100),
            )
        )

    assert results.count(True) == 1
    assert results.count(False) == 99

    rows = db.conn.execute(
        """
        SELECT COUNT(*)
        FROM paper_trades
        WHERE token='0xabc'
          AND status='OPEN'
        """
    ).fetchone()[0]

    assert rows == 1

    _reset_database()


def test_concurrent_different_tokens(
    tmp_path,
    monkeypatch,
):
    _reset_database()

    monkeypatch.setattr(
        database_module,
        "DB",
        tmp_path / "paper.db",
    )

    db = PaperDatabase()

    def worker(i):
        return db.insert_if_no_open_position(
            _trade(f"0x{i:040x}")
        )

    with ThreadPoolExecutor(
        max_workers=16
    ) as executor:
        results = list(
            executor.map(
                worker,
                range(200),
            )
        )

    assert all(results)

    rows = db.conn.execute(
        """
        SELECT COUNT(*)
        FROM paper_trades
        WHERE status='OPEN'
        """
    ).fetchone()[0]

    assert rows == 200

    _reset_database()


def test_parallel_reads_are_safe(
    tmp_path,
    monkeypatch,
):
    _reset_database()

    monkeypatch.setattr(
        database_module,
        "DB",
        tmp_path / "paper.db",
    )

    db = PaperDatabase()

    assert db.insert_if_no_open_position(
        _trade("0xabc")
    )

    def worker(_):
        return db.has_open_position(
            "0xabc"
        )

    with ThreadPoolExecutor(
        max_workers=16
    ) as executor:
        results = list(
            executor.map(
                worker,
                range(500),
            )
        )

    assert all(results)

    _reset_database()


def test_close_does_not_mutate_input(
    tmp_path,
    monkeypatch,
):
    _reset_database()

    monkeypatch.setattr(
        database_module,
        "DB",
        tmp_path / "paper.db",
    )

    db = PaperDatabase()

    db.insert(
        _trade("0xabc")
    )

    trade_id = db.conn.execute(
        """
        SELECT id
        FROM paper_trades
        WHERE token='0xabc'
        """
    ).fetchone()[0]

    values = {
        "close_reason": "TEST"
    }

    db.close_position(
        trade_id,
        values,
    )

    assert values == {
        "close_reason": "TEST"
    }

    _reset_database()
