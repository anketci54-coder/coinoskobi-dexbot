import sqlite3

from app.dex.arkham_successful_wallet_service import ArkhamSuccessfulWalletService
from app.paper.wallet_holdings_schema import ensure_wallet_holdings_schema


def test_partial_snapshot_does_not_claim_newly_visible_token_was_added(tmp_path):
    path = tmp_path / "paper.db"
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
        INSERT INTO wallet_discovery_registry
        VALUES('bsc:wallet','bsc','0xwallet','TRANSACTION_FROM_ONLY');
        INSERT INTO wallet_success_score
        VALUES('bsc:wallet',1,'SUCCESSFUL');
        """
    )
    ensure_wallet_holdings_schema(db)
    db.close()

    def row(token, value):
        return {
            "token_id": f"bsc:{token}",
            "token_address": token,
            "balance": 1.0,
            "value_usd": value,
        }

    responses = iter([
        {
            "available": True,
            "holdings": [row("0xaaa", 10)],
            "complete_snapshot": True,
            "available_asset_count": 1,
            "fetched_at": 100.0,
        },
        {
            "available": True,
            "holdings": [row("0xaaa", 11), row("0xbbb", 20)],
            "complete_snapshot": False,
            "provider_state": "PARTIAL_ASSET_CAP",
            "available_asset_count": 129,
            "fetched_at": 200.0,
        },
    ])

    service = ArkhamSuccessfulWalletService(
        path,
        fetcher=lambda *args, **kwargs: next(responses),
    )
    service.run_cycle()
    second = service.run_cycle()

    assert second["change_events"] == 0
    db = sqlite3.connect(path)
    rows = db.execute(
        "SELECT change_type,token_id FROM wallet_holding_change_evidence "
        "WHERE observed_at=200 ORDER BY token_id"
    ).fetchall()
    db.close()
    assert rows == []
