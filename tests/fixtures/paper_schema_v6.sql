-- Frozen PAPER core schema from d8da433865456e35dae0c2af05038cf376446978.
-- Test fixture only; never execute against a deployed database.

CREATE TABLE counterfactual_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    token TEXT NOT NULL,
    pool TEXT NOT NULL,

    observed_at REAL NOT NULL,
    entry_price REAL NOT NULL,

    signal_state TEXT NOT NULL,
    candidate_action TEXT NOT NULL,

    context_json TEXT NOT NULL DEFAULT '{}',

    last_observed_at REAL,
    last_price REAL,

    max_price REAL,
    min_price REAL,

    price_5m REAL,
    return_5m REAL,
    observed_5m_at REAL,

    price_15m REAL,
    return_15m REAL,
    observed_15m_at REAL,

    price_30m REAL,
    return_30m REAL,
    observed_30m_at REAL,

    price_60m REAL,
    return_60m REAL,
    observed_60m_at REAL,

    completed_at REAL
);

CREATE TABLE paper_price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    position_id INTEGER NOT NULL,

    observed_at TEXT NOT NULL,

    price REAL NOT NULL,

    FOREIGN KEY(position_id)
    REFERENCES paper_trades(id)
);

CREATE TABLE paper_realizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    position_id INTEGER NOT NULL,

    stage TEXT NOT NULL,

    observed_at TEXT NOT NULL,

    price REAL NOT NULL,

    token_amount REAL NOT NULL,

    close_fraction REAL NOT NULL,

    gross_proceeds_usdt REAL NOT NULL,
    net_proceeds_usdt REAL NOT NULL,

    sold_cost_basis_usdt REAL NOT NULL,

    realized_pnl_usdt REAL NOT NULL,
    execution_evidence_json TEXT,

    FOREIGN KEY(position_id)
    REFERENCES paper_trades(id)
);

CREATE TABLE paper_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_key TEXT NOT NULL UNIQUE,
    started_at REAL NOT NULL,
    starting_capital_usdt REAL NOT NULL,
    start_trade_id INTEGER NOT NULL,
    start_realization_id INTEGER NOT NULL,
    start_candidate_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE TABLE paper_trades (
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
    status TEXT,

    token_amount REAL DEFAULT 0,

    pool TEXT,
    dex TEXT,

    opening_context_json TEXT,
    paper_run_id INTEGER REFERENCES paper_runs(id),
    closing_execution_json TEXT,

    paper_account_version TEXT,
    trade_policy TEXT,
    control_mode TEXT,
    trade_type TEXT,
    level_source TEXT,

    entry_amount_usdt REAL,
    risk_amount_usdt REAL,

    capital_before_usdt REAL,
    capital_after_entry_usdt REAL,

    position_size_pct REAL,
    sizing_reason TEXT,

    gross_pnl_usdt REAL,
    net_pnl_usdt REAL,

    initial_token_amount REAL,

    remaining_cost_basis_usdt REAL,

    realized_gross_proceeds_usdt REAL DEFAULT 0,
    realized_proceeds_usdt REAL DEFAULT 0,
    realized_pnl_usdt REAL DEFAULT 0,

    tp1_done INTEGER DEFAULT 0,
    tp2_done INTEGER DEFAULT 0,
    runner_active INTEGER DEFAULT 0,

    mathematical_plan_json TEXT,
    math_state_json TEXT,

    cost_model_complete INTEGER DEFAULT 0
);

CREATE INDEX idx_counterfactual_observations_pending
    ON counterfactual_observations(
        token,
        completed_at,
        observed_at
    )
    ;

CREATE INDEX idx_paper_price_observations_position
    ON paper_price_observations(position_id, id)
    ;

CREATE INDEX idx_paper_realizations_position
    ON paper_realizations(position_id, id)
    ;

CREATE UNIQUE INDEX idx_paper_trades_one_open_per_token
ON paper_trades(lower(token))
WHERE status='OPEN'
AND token IS NOT NULL
;

CREATE INDEX idx_paper_trades_status
    ON paper_trades(status)
    ;

CREATE INDEX idx_paper_trades_token_status
    ON paper_trades(token, status)
    ;

PRAGMA user_version=6;
