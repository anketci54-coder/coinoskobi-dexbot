import sqlite3

from app.api import panel_acceptance
from app.api.panel_acceptance import wallet_intelligence_detail
from app.paper.wallet_holdings_schema import ensure_wallet_holdings_schema


def _db(path):
    con = sqlite3.connect(path)
    con.executescript(
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
            sample_depth INTEGER,
            qualification_state TEXT
        );
        CREATE TABLE intelligence_summary_readmodel(
            summary_key TEXT PRIMARY KEY,
            generated_at TEXT,
            tracked_wallets INTEGER,
            successful_wallets INTEGER,
            active_whales INTEGER,
            wallet_details_json TEXT
        );
        INSERT INTO wallet_discovery_registry
        VALUES('bsc:wallet','bsc','0xabc','TRANSACTION_FROM_ONLY');
        INSERT INTO wallet_success_score
        VALUES('bsc:wallet',100,25,'SUCCESSFUL');
        INSERT INTO intelligence_summary_readmodel
        VALUES('PHASE9_PANEL_DETAIL','2026-09-05T09:00:00+00:00',1,1,0,'[]');
        """
    )
    ensure_wallet_holdings_schema(con)
    con.execute(
        """
        INSERT INTO wallet_holding_snapshot(
            wallet_uid,token_id,chain,address,token_address,symbol,name,
            balance,value_usd,price_usd,price_change_24h_pct,observed_at,provider
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            'bsc:wallet','bsc:0xtoken','bsc','0xabc','0xtoken','TOK','Token',
            5.0,50.0,10.0,2.5,200.0,'ARKHAM',
        ),
    )
    con.execute(
        """
        INSERT INTO wallet_holding_scan_state(
            wallet_uid,last_scan_at,last_success_at,last_provider_state,
            total_value_usd,asset_count
        ) VALUES(?,?,?,?,?,?)
        """,
        ('bsc:wallet',200.0,200.0,'READY',50.0,1),
    )
    con.execute(
        """
        INSERT INTO wallet_holding_change_evidence(
            wallet_uid,token_id,change_type,previous_balance,current_balance,
            previous_value_usd,current_value_usd,observed_at,provider
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        ('bsc:wallet','bsc:0xtoken','INCREASED',4.0,5.0,40.0,50.0,200.0,'ARKHAM'),
    )
    con.commit()
    con.close()


def test_wallet_panel_returns_successful_wallet_holdings_and_changes(tmp_path, monkeypatch):
    path = tmp_path / 'paper.db'
    _db(path)
    monkeypatch.setattr(
        panel_acceptance,
        'arkham_config_status',
        lambda: {'provider': 'ARKHAM', 'configured': True},
    )

    out = wallet_intelligence_detail(path)

    assert out['available'] is True
    assert out['successful_wallets'] == 1
    assert isinstance(out['generated_at'], float)
    assert out['generated_at'] > 0
    holdings = out['arkham_holdings']
    assert holdings['state'] == 'READY'
    assert holdings['wallet_count'] == 1
    assert holdings['wallets'][0]['address'] == '0xabc'
    assert holdings['wallets'][0]['total_value_usd'] == 50.0
    assert holdings['wallets'][0]['holdings'][0]['symbol'] == 'TOK'
    assert holdings['changes'][0]['change_type'] == 'INCREASED'
    assert holdings['read_only'] is True
    assert holdings['trade_authority'] is False
    assert holdings['decision_authority'] is False
    assert holdings['paper_authority'] is False
    assert holdings['wallet_authority'] is False
    assert holdings['signing_authority'] is False
    assert holdings['execution_authority'] is False


def test_wallet_panel_reports_key_absence_without_fake_holdings(tmp_path, monkeypatch):
    path = tmp_path / 'paper.db'
    _db(path)
    monkeypatch.setattr(
        panel_acceptance,
        'arkham_config_status',
        lambda: {'provider': 'ARKHAM', 'configured': False},
    )

    out = wallet_intelligence_detail(path)

    holdings = out['arkham_holdings']
    assert holdings['state'] == 'INACTIVE_NO_API_KEY'
    assert holdings['wallet_count'] == 1
    assert holdings['wallets'][0]['holdings'][0]['symbol'] == 'TOK'
    assert out['provider']['configured'] is False


def test_wallet_panel_no_successful_wallets_is_explicit(tmp_path, monkeypatch):
    path = tmp_path / 'paper.db'
    _db(path)
    con = sqlite3.connect(path)
    con.execute("UPDATE wallet_success_score SET qualification_state='OBSERVED'")
    con.commit()
    con.close()
    monkeypatch.setattr(
        panel_acceptance,
        'arkham_config_status',
        lambda: {'provider': 'ARKHAM', 'configured': True},
    )

    out = wallet_intelligence_detail(path)

    holdings = out['arkham_holdings']
    assert holdings['state'] == 'NO_SUCCESSFUL_WALLETS'
    assert holdings['wallets'] == []
    assert holdings['changes'] == []
