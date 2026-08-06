class PaperCalculator:

    def net_pnl_percent(
        self,
        gross_percent,
        buy_tax,
        sell_tax,
        swap_fee,
        slippage,
        mev
    ):

        total_cost = (
            buy_tax +
            sell_tax +
            swap_fee +
            slippage +
            mev
        )

        return gross_percent - total_cost
