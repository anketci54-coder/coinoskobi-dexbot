import sqlite3
import threading
import time

from app.dex import arkham_provider
from app.dex.arkham_successful_wallet_service import ArkhamSuccessfulWalletService
from app.paper.wallet_holdings_schema import ensure_wallet_holdings_schema


def _create_phase9_tables(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE wallet_discovery_registry(
            wallet_uid TEXT PRIMARY KEY,
            chain TEXT,
            address TEXT,
            discovery_source TEXT
        );
        CREATE TABLE wallet_success_score(
            wallet_uid TEXT PRIMARY KEY,
            calculated_at REAL,
            qualification_state TEXT
        );
        """
    )
    ensure_wallet_holdings_schema(db)
    db.close()


def _insert_wallet(path, index, *, calculated_at=None):
    wallet_uid = f"bsc:0x{index:040x}"
    address = f"0x{index:040x}"
    db = sqlite3.connect(path)
    db.execute(
        "INSERT INTO wallet_discovery_registry VALUES(?,?,?,'TRANSACTION_FROM_ONLY')",
        (wallet_uid, "bsc", address),
    )
    db.execute(
        "INSERT INTO wallet_success_score VALUES(?,?,'SUCCESSFUL')",
        (wallet_uid, float(index if calculated_at is None else calculated_at)),
    )
    db.commit()
    db.close()
    return wallet_uid, address


def _holding(token, balance, value):
    return {
        "token_id": f"bsc:{token}",
        "token_address": token,
        "pricing_id": None,
        "symbol": token[-3:].upper(),
        "name": token,
        "balance": balance,
        "value_usd": value,
        "price_usd": None,
        "price_change_24h_pct": None,
    }


def _snapshot(*holdings, fetched_at, complete=True, available_count=None, provider_state=None):
    rows = list(holdings)
    result = {
        "available": True,
        "chain": "bsc",
        "holdings": rows,
        "total_value_usd": sum(float(row.get("value_usd") or 0) for row in rows),
        "complete_snapshot": complete,
        "available_asset_count": available_count if available_count is not None else len(rows),
        "fetched_at": float(fetched_at),
    }
    if provider_state is not None:
        result["provider_state"] = provider_state
    return result


def _query(path, sql, params=()):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in db.execute(sql, params).fetchall()]
    finally:
        db.close()


def test_provider_marks_capped_129_asset_response_partial(monkeypatch):
    payload = {
        "balances": {
            "bsc": [
                {
                    "ethereumAddress": f"0x{i:040x}",
                    "symbol": f"T{i}",
                    "balance": 1,
                    "usd": float(i),
                }
                for i in range(129)
            ]
        },
        "totalBalance": {"bsc": 8256.0},
    }

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return payload

    monkeypatch.setenv("ARKHAM_API_KEY", "test-key")
    monkeypatch.setattr(arkham_provider.requests, "get", lambda *args, **kwargs: Response())

    out = arkham_provider.fetch_balances_for_address("0xwallet", chain="bsc")

    assert out["complete_snapshot"] is False
    assert out["provider_state"] == "PARTIAL_ASSET_CAP"
    assert out["available_asset_count"] == 129
    assert out["returned_asset_count"] == 128
    assert len(out["holdings"]) == 128


def test_provider_rejects_malformed_requested_chain_rows(monkeypatch):
    payload = {
        "balances": {"bsc": {"unexpected": "mapping"}},
        "totalBalance": {"bsc": 123.0},
    }

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return payload

    monkeypatch.setenv("ARKHAM_API_KEY", "test-key")
    monkeypatch.setattr(arkham_provider.requests, "get", lambda *args, **kwargs: Response())

    out = arkham_provider.fetch_balances_for_address("0xwallet", chain="bsc")

    assert out["available"] is False
    assert out["reason"] == "ARKHAM_INVALID_CHAIN_BALANCES"
    assert out["holdings"] == []


def test_provider_rejected_rows_make_snapshot_partial(monkeypatch):
    payload = {
        "balances": {
            "bsc": [
                {
                    "ethereumAddress": "0x0000000000000000000000000000000000000001",
                    "symbol": "GOOD",
                    "balance": 1,
                    "usd": 10,
                },
                {"symbol": "BAD", "balance": "not-a-number"},
            ]
        },
        "totalBalance": {"bsc": 10.0},
    }

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return payload

    monkeypatch.setenv("ARKHAM_API_KEY", "test-key")
    monkeypatch.setattr(arkham_provider.requests, "get", lambda *args, **kwargs: Response())

    out = arkham_provider.fetch_balances_for_address("0xwallet", chain="bsc")

    assert out["available"] is True
    assert out["complete_snapshot"] is False
    assert out["provider_state"] == "PARTIAL_REJECTED_ROWS"
    assert out["available_asset_count"] == 2
    assert out["valid_asset_count"] == 1
    assert out["rejected_asset_count"] == 1


def test_partial_capped_snapshot_preserves_omitted_prior_assets_and_no_removal(tmp_path):
    path = tmp_path / "paper.db"
    _create_phase9_tables(path)
    _insert_wallet(path, 1)
    results = iter(
        [
            _snapshot(
                _holding("0xaaa", 5, 50),
                _holding("0xbbb", 2, 20),
                fetched_at=100,
            ),
            _snapshot(
                _holding("0xaaa", 8, 80),
                fetched_at=200,
                complete=False,
                available_count=129,
                provider_state="PARTIAL_ASSET_CAP",
            ),
        ]
    )

    service = ArkhamSuccessfulWalletService(path, fetcher=lambda *args, **kwargs: next(results))
    service.run_cycle()
    second = service.run_cycle()

    assert second["change_events"] == 1
    assert _query(
        path,
        "SELECT token_id,balance FROM wallet_holding_snapshot ORDER BY token_id",
    ) == [
        {"token_id": "bsc:0xaaa", "balance": 8.0},
        {"token_id": "bsc:0xbbb", "balance": 2.0},
    ]
    assert _query(
        path,
        "SELECT change_type FROM wallet_holding_change_evidence WHERE observed_at=200",
    ) == [{"change_type": "INCREASED"}]
    state = _query(
        path,
        "SELECT last_provider_state,asset_count FROM wallet_holding_scan_state",
    )[0]
    assert state == {"last_provider_state": "PARTIAL_ASSET_CAP", "asset_count": 129}


def test_successive_partial_snapshots_never_grow_past_asset_cap(tmp_path):
    path = tmp_path / "paper.db"
    _create_phase9_tables(path)
    _insert_wallet(path, 1)

    first = [
        _holding(f"0x{i:040x}", 1, 1000 - i)
        for i in range(128)
    ]
    second = [
        _holding(f"0x{i:040x}", 1, 2000 - i)
        for i in range(64, 192)
    ]
    results = iter([
        _snapshot(*first, fetched_at=100, complete=False, available_count=192, provider_state="PARTIAL_ASSET_CAP"),
        _snapshot(*second, fetched_at=200, complete=False, available_count=192, provider_state="PARTIAL_ASSET_CAP"),
    ])

    service = ArkhamSuccessfulWalletService(path, fetcher=lambda *args, **kwargs: next(results))
    service.run_cycle()
    service.run_cycle()

    count = _query(path, "SELECT COUNT(*) AS n FROM wallet_holding_snapshot")[0]["n"]
    assert count == 128
    removed = _query(
        path,
        "SELECT COUNT(*) AS n FROM wallet_holding_change_evidence WHERE change_type='REMOVED'",
    )[0]["n"]
    assert removed == 0


def test_tracked_cohort_never_rotates_beyond_500_successful_wallets(tmp_path):
    path = tmp_path / "paper.db"
    _create_phase9_tables(path)
    excluded_uid = None
    for index in range(501):
        uid, _ = _insert_wallet(path, index, calculated_at=index)
        if index == 0:
            excluded_uid = uid

    db = sqlite3.connect(path)
    for index in range(1, 501):
        db.execute(
            """
            INSERT INTO wallet_holding_scan_state(
                wallet_uid,last_scan_at,last_provider_state
            ) VALUES(?,100,'READY')
            """,
            (f"bsc:0x{index:040x}",),
        )
    db.commit()
    db.row_factory = sqlite3.Row
    try:
        selected = ArkhamSuccessfulWalletService._qualified_wallets(db, 1)
    finally:
        db.close()

    assert len(selected) == 1
    assert selected[0]["wallet_uid"] != excluded_uid
    assert selected[0]["wallet_uid"] == "bsc:0x00000000000000000000000000000000000001f4"


def test_displaced_wallet_state_is_pruned_from_500_wallet_cohort(tmp_path):
    path = tmp_path / "paper.db"
    _create_phase9_tables(path)
    for index in range(501):
        _insert_wallet(path, index, calculated_at=index)

    displaced_uid = "bsc:0x0000000000000000000000000000000000000000"
    db = sqlite3.connect(path)
    db.execute(
        "INSERT INTO wallet_holding_scan_state(wallet_uid,last_scan_at,last_provider_state) VALUES(?,1,'READY')",
        (displaced_uid,),
    )
    db.execute(
        """
        INSERT INTO wallet_holding_snapshot(
            wallet_uid,token_id,chain,address,balance,observed_at,provider
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (displaced_uid, "bsc:0xdead", "bsc", "0x0", 1, 1, "ARKHAM"),
    )
    db.commit()
    db.close()

    service = ArkhamSuccessfulWalletService(
        path,
        fetcher=lambda *args, **kwargs: {"available": False, "reason": "STOP"},
        wallets_per_cycle=1,
    )
    service.run_cycle()

    assert _query(
        path,
        "SELECT wallet_uid FROM wallet_holding_scan_state WHERE wallet_uid=?",
        (displaced_uid,),
    ) == []
    assert _query(
        path,
        "SELECT wallet_uid FROM wallet_holding_snapshot WHERE wallet_uid=?",
        (displaced_uid,),
    ) == []


def test_provider_network_wait_happens_without_prior_wallet_write_lock(tmp_path):
    path = tmp_path / "paper.db"
    _create_phase9_tables(path)
    _insert_wallet(path, 1, calculated_at=2)
    _insert_wallet(path, 2, calculated_at=1)
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE lock_probe(id INTEGER PRIMARY KEY)")
    db.commit()
    db.close()
    calls = 0

    def fetcher(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _snapshot(_holding("0xaaa", 1, 10), fetched_at=100)

        writer = sqlite3.connect(path, timeout=0.2)
        try:
            writer.execute("INSERT INTO lock_probe(id) VALUES(1)")
            writer.commit()
        finally:
            writer.close()
        return {"available": False, "reason": "ARKHAM_HTTP_429", "holdings": []}

    out = ArkhamSuccessfulWalletService(path, fetcher=fetcher, wallets_per_cycle=2).run_cycle()

    assert out["state"] == "PARTIAL"
    assert out["wallets_updated"] == 1
    assert out["provider_failures"] == 1
    assert _query(path, "SELECT id FROM lock_probe") == [{"id": 1}]


def test_truthy_non_dict_provider_failure_is_fail_soft_and_advances_scan_state(tmp_path):
    path = tmp_path / "paper.db"
    _create_phase9_tables(path)
    uid, _ = _insert_wallet(path, 1)

    out = ArkhamSuccessfulWalletService(path, fetcher=lambda *args, **kwargs: "bad-response").run_cycle()

    assert out["state"] == "PROVIDER_UNAVAILABLE"
    assert out["provider_failures"] == 1
    state = _query(
        path,
        "SELECT wallet_uid,last_provider_state FROM wallet_holding_scan_state",
    )[0]
    assert state["wallet_uid"] == uid
    assert state["last_provider_state"] == "UNAVAILABLE"


def test_stop_cancels_between_wallets_and_waits_for_worker_exit(tmp_path):
    path = tmp_path / "paper.db"
    _create_phase9_tables(path)
    _insert_wallet(path, 1, calculated_at=2)
    _insert_wallet(path, 2, calculated_at=1)

    entered = threading.Event()
    release = threading.Event()
    calls = []

    def fetcher(address, **kwargs):
        calls.append(address)
        entered.set()
        release.wait(timeout=2)
        return {"available": False, "reason": "ARKHAM_HTTP_429", "holdings": []}

    service = ArkhamSuccessfulWalletService(
        path,
        fetcher=fetcher,
        wallets_per_cycle=2,
        interval_seconds=30,
    )
    service.start()
    assert entered.wait(timeout=2)

    stopper = threading.Thread(target=service.stop)
    stopper.start()
    time.sleep(0.05)
    assert stopper.is_alive()

    release.set()
    stopper.join(timeout=2)

    assert not stopper.is_alive()
    assert service.status()["state"] == "STOPPED"
    assert len(calls) == 1
