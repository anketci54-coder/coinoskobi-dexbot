import sqlite3

from app.dex.arkham_successful_wallet_service import ArkhamSuccessfulWalletService
from app.paper.wallet_holdings_schema import ensure_wallet_holdings_schema


WALLET = "bsc:0xabc"
ADDRESS = "0xabc"


def phase9_db(path, *, state="SUCCESSFUL"):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE wallet_discovery_registry(
            wallet_uid TEXT PRIMARY KEY,
            chain TEXT,
            address TEXT,
            first_seen_at REAL,
            last_seen_at REAL,
            discovery_source TEXT,
            freshness_state TEXT,
            lifecycle_state TEXT
        );
        CREATE TABLE wallet_success_score(
            wallet_uid TEXT PRIMARY KEY,
            calculated_at REAL,
            sample_depth INTEGER,
            qualification_state TEXT
        );
        """
    )
    db.execute(
        """
        INSERT INTO wallet_discovery_registry(
            wallet_uid,chain,address,first_seen_at,last_seen_at,
            discovery_source,freshness_state,lifecycle_state
        ) VALUES(?,?,?,?,?,'TRANSACTION_FROM_ONLY','FRESH','ACTIVE')
        """,
        (WALLET, "bsc", ADDRESS, 1, 2),
    )
    db.execute(
        """
        INSERT INTO wallet_success_score(
            wallet_uid,calculated_at,sample_depth,qualification_state
        ) VALUES(?,?,?,?)
        """,
        (WALLET, 2, 20, state),
    )
    ensure_wallet_holdings_schema(db)
    db.close()


def snapshot(*rows, fetched_at=100.0, total=100.0):
    return {
        "available": True,
        "chain": "bsc",
        "address": ADDRESS,
        "holdings": list(rows),
        "total_value_usd": total,
        "complete_snapshot": True,
        "fetched_at": fetched_at,
    }


def holding(token, balance, value):
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


def rows(path, sql):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in db.execute(sql).fetchall()]
    finally:
        db.close()


def test_non_successful_wallet_is_never_sent_to_arkham(tmp_path):
    path = tmp_path / "paper.db"
    phase9_db(path, state="OBSERVED")
    calls = []

    service = ArkhamSuccessfulWalletService(
        path,
        fetcher=lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    out = service.run_cycle()

    assert out["state"] == "NO_SUCCESSFUL_WALLETS"
    assert out["wallets_requested"] == 0
    assert calls == []
    assert out["decision_authority"] is False
    assert out["wallet_authority"] is False
    assert out["execution_authority"] is False


def test_successful_wallet_snapshot_is_persisted_and_runtime_observed(tmp_path):
    path = tmp_path / "paper.db"
    phase9_db(path)
    observed = []

    class Intelligence:
        @staticmethod
        def observe_wallet_holding(*args, **kwargs):
            observed.append((args, kwargs))
            return {"state": "READY"}

    service = ArkhamSuccessfulWalletService(
        path,
        intelligence=Intelligence(),
        fetcher=lambda *args, **kwargs: snapshot(
            holding("0xaaa", 5, 50),
            holding("0xbbb", 2, 40),
            total=90,
        ),
    )
    out = service.run_cycle()

    assert out["state"] == "READY"
    assert out["wallets_updated"] == 1
    assert out["change_events"] == 2

    persisted = rows(
        path,
        "SELECT token_id,balance,value_usd,provider FROM wallet_holding_snapshot ORDER BY token_id",
    )
    assert [row["token_id"] for row in persisted] == ["bsc:0xaaa", "bsc:0xbbb"]
    assert all(row["provider"] == "ARKHAM" for row in persisted)

    state = rows(
        path,
        "SELECT total_value_usd,asset_count,last_provider_state FROM wallet_holding_scan_state",
    )[0]
    assert state == {
        "total_value_usd": 90.0,
        "asset_count": 2,
        "last_provider_state": "READY",
    }
    assert {call[0][1] for call in observed} == {"bsc:0xaaa", "bsc:0xbbb"}


def test_second_complete_snapshot_records_added_increased_and_removed(tmp_path):
    path = tmp_path / "paper.db"
    phase9_db(path)
    snapshots = iter(
        [
            snapshot(
                holding("0xaaa", 5, 50),
                holding("0xbbb", 2, 40),
                fetched_at=100,
                total=90,
            ),
            snapshot(
                holding("0xaaa", 8, 80),
                holding("0xccc", 1, 20),
                fetched_at=200,
                total=100,
            ),
        ]
    )

    service = ArkhamSuccessfulWalletService(
        path,
        fetcher=lambda *args, **kwargs: next(snapshots),
    )
    first = service.run_cycle()
    second = service.run_cycle()

    assert first["change_events"] == 2
    assert second["change_events"] == 3

    changes = rows(
        path,
        """
        SELECT token_id,change_type,previous_balance,current_balance
        FROM wallet_holding_change_evidence
        WHERE observed_at=200
        ORDER BY token_id
        """,
    )
    assert changes == [
        {
            "token_id": "bsc:0xaaa",
            "change_type": "INCREASED",
            "previous_balance": 5.0,
            "current_balance": 8.0,
        },
        {
            "token_id": "bsc:0xbbb",
            "change_type": "REMOVED",
            "previous_balance": 2.0,
            "current_balance": None,
        },
        {
            "token_id": "bsc:0xccc",
            "change_type": "ADDED",
            "previous_balance": None,
            "current_balance": 1.0,
        },
    ]

    current = rows(
        path,
        "SELECT token_id,balance FROM wallet_holding_snapshot ORDER BY token_id",
    )
    assert current == [
        {"token_id": "bsc:0xaaa", "balance": 8.0},
        {"token_id": "bsc:0xccc", "balance": 1.0},
    ]


def test_provider_failure_does_not_erase_last_good_snapshot(tmp_path):
    path = tmp_path / "paper.db"
    phase9_db(path)
    results = iter(
        [
            snapshot(holding("0xaaa", 5, 50), total=50),
            {"available": False, "reason": "ARKHAM_HTTP_429", "holdings": []},
        ]
    )

    service = ArkhamSuccessfulWalletService(
        path,
        fetcher=lambda *args, **kwargs: next(results),
    )
    assert service.run_cycle()["state"] == "READY"
    failed = service.run_cycle()

    assert failed["state"] == "PROVIDER_UNAVAILABLE"
    assert rows(
        path,
        "SELECT token_id,balance FROM wallet_holding_snapshot",
    ) == [{"token_id": "bsc:0xaaa", "balance": 5.0}]
    state = rows(
        path,
        "SELECT last_provider_state,asset_count FROM wallet_holding_scan_state",
    )[0]
    assert state["last_provider_state"] == "ARKHAM_HTTP_429"
    assert state["asset_count"] == 1


def test_removed_asset_is_zeroed_in_runtime_readmodel(tmp_path):
    path = tmp_path / "paper.db"
    phase9_db(path)
    results = iter(
        [
            snapshot(holding("0xaaa", 5, 50), total=50),
            snapshot(fetched_at=200, total=0),
        ]
    )
    observed = []

    class Intelligence:
        @staticmethod
        def observe_wallet_holding(*args, **kwargs):
            observed.append((args, kwargs))
            return {"state": "READY"}

    service = ArkhamSuccessfulWalletService(
        path,
        intelligence=Intelligence(),
        fetcher=lambda *args, **kwargs: next(results),
    )
    service.run_cycle()
    service.run_cycle()

    zero = [call for call in observed if call[0][1] == "bsc:0xaaa" and call[0][2] == 0.0]
    assert len(zero) == 1
    assert zero[0][1]["value_usd"] == 0.0
