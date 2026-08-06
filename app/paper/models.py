from dataclasses import dataclass
from datetime import datetime

@dataclass
class PaperTrade:

    token: str
    symbol: str

    amount_bnb: float

    entry_price: float

    tp_percent: float = 20.0
    sl_percent: float = 10.0

    buy_gas_bnb: float = 0.00018
    sell_gas_bnb: float = 0.00018

    swap_fee_percent: float = 0.25

    buy_tax_percent: float = 0.0
    sell_tax_percent: float = 0.0

    estimated_slippage_percent: float = 0.50

    estimated_mev_percent: float = 0.20

    opened_at: str = datetime.utcnow().isoformat()

    status: str = "OPEN"
