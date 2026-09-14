from pathlib import Path

from app.paper.control_mode import set_control_mode


def _paper_database(tmp_path, monkeypatch):
    import app.paper.database as database_module

    db_path = tmp_path / "paper.db"

    monkeypatch.setattr(
        database_module,
        "DB",
        db_path,
    )

    database_module.PaperDatabase._instance = None
    database_module.PaperDatabase._initialized = False

    paper = database_module.PaperDatabase()

    return (
        database_module,
        paper,
        db_path,
    )


def _reset(database_module, paper):
    try:
        paper.conn.close()
    except Exception:
        pass

    database_module.PaperDatabase._instance = None
    database_module.PaperDatabase._initialized = False


def _trade():
    return {
        "token": "0xabc",
        "symbol": "TEST",
        "entry_price": 1.0,
        "current_price": 1.0,
        "highest_price": 1.0,
        "lowest_price": 1.0,
        "tp_price": 1.2,
        "sl_price": 0.9,
        "amount_bnb": 0.0,
        "status": "OPEN",
        "token_amount": 100.0,
        "initial_token_amount": 100.0,
        "pool": "0xpool",
        "paper_account_version": "PAPER_10K_V2",
        "entry_amount_usdt": 100.0,
        "remaining_cost_basis_usdt": 100.0,
        "control_mode": "AUTO",
        "trade_type": "NORMAL",
        "level_source": "SYSTEM",
    }


def test_manual_runtime_mode_blocks_new_auto_insert(
    tmp_path: Path,
    monkeypatch,
):
    (
        database_module,
        paper,
        db_path,
    ) = _paper_database(
        tmp_path,
        monkeypatch,
    )

    try:
        set_control_mode(
            db_path,
            "MANUAL",
        )

        assert (
            paper.insert_if_below_open_limit(
                _trade(),
                5,
            )
            is False
        )

        count = paper.conn.execute(
            """
            SELECT COUNT(*)
            FROM paper_trades
            """
        ).fetchone()[0]

        assert count == 0

    finally:
        _reset(
            database_module,
            paper,
        )


def test_manual_runtime_mode_does_not_block_manual_insert(
    tmp_path: Path,
    monkeypatch,
):
    (
        database_module,
        paper,
        db_path,
    ) = _paper_database(
        tmp_path,
        monkeypatch,
    )

    try:
        set_control_mode(
            db_path,
            "MANUAL",
        )

        trade = _trade()
        trade["control_mode"] = "MANUAL"
        trade["trade_policy"] = "MANUAL_PANEL"

        assert (
            paper.insert_if_below_open_limit(
                trade,
                5,
            )
            is True
        )

    finally:
        _reset(
            database_module,
            paper,
        )


def test_auto_runtime_mode_allows_auto_insert(
    tmp_path: Path,
    monkeypatch,
):
    (
        database_module,
        paper,
        db_path,
    ) = _paper_database(
        tmp_path,
        monkeypatch,
    )

    try:
        set_control_mode(
            db_path,
            "AUTO",
        )

        assert (
            paper.insert_if_below_open_limit(
                _trade(),
                5,
            )
            is True
        )

    finally:
        _reset(
            database_module,
            paper,
        )
