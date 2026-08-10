def _number(value):
    if value is None:
        return None

    try:
        value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if value < 0:
        return None

    return value


class ExecutionCostEngine:
    """
    Execution Cost v1.

    Pure-local economic calculator.

    It does NOT:
    - call RPC / HTTP
    - invent missing costs
    - open positions
    - calculate Entry / SL / TP
    - create live authority

    Unknown cost remains UNKNOWN.

    Percentage cost dimensions:
    - buy tax
    - sell tax
    - swap fee
    - slippage
    - MEV cost

    Fixed gas cost:
    - gas_cost_usd

    Gas can be converted to percentage only when
    trade_size_usd is also known.
    """

    REQUIRED_PERCENT_FIELDS = (
        "buy_tax_pct",
        "sell_tax_pct",
        "swap_fee_pct",
        "slippage_pct",
        "mev_cost_pct",
    )

    def evaluate(self, context):
        context = context or {}

        trade_size_usd = _number(
            context.get(
                "trade_size_usd"
            )
        )

        gas_cost_usd = _number(
            context.get(
                "gas_cost_usd"
            )
        )

        expected_gross_edge_pct = _number(
            context.get(
                "expected_gross_edge_pct"
            )
        )

        percent_values = {}

        for field in (
            self.REQUIRED_PERCENT_FIELDS
        ):
            percent_values[field] = (
                _number(
                    context.get(field)
                )
            )

        known_percent_cost = sum(
            value
            for value
            in percent_values.values()
            if value is not None
        )

        unknown_components = [
            field
            for (
                field,
                value,
            ) in percent_values.items()
            if value is None
        ]

        gas_cost_pct = None

        if gas_cost_usd is None:
            unknown_components.append(
                "gas_cost_usd"
            )

        elif (
            trade_size_usd is None
            or trade_size_usd <= 0
        ):
            unknown_components.append(
                "trade_size_usd_for_gas"
            )

        else:
            gas_cost_pct = (
                gas_cost_usd
                / trade_size_usd
                * 100.0
            )

        known_total_cost_pct = (
            known_percent_cost
            + (
                gas_cost_pct
                if gas_cost_pct is not None
                else 0.0
            )
        )

        cost_complete = (
            len(unknown_components) == 0
        )

        net_edge_pct = None
        break_even_edge_pct = None

        if cost_complete:
            break_even_edge_pct = (
                known_total_cost_pct
            )

            if (
                expected_gross_edge_pct
                is not None
            ):
                net_edge_pct = (
                    expected_gross_edge_pct
                    - known_total_cost_pct
                )

        # --------------------------------------------------------
        # Feasibility
        #
        # Without complete cost evidence and expected edge,
        # we refuse to pretend the economics are known.
        # --------------------------------------------------------

        if not cost_complete:
            feasibility = "UNKNOWN_COST"

        elif (
            expected_gross_edge_pct
            is None
        ):
            feasibility = (
                "COST_KNOWN_EDGE_UNKNOWN"
            )

        elif net_edge_pct > 0:
            feasibility = (
                "POSITIVE_NET_EDGE"
            )

        elif net_edge_pct == 0:
            feasibility = "BREAK_EVEN"

        else:
            feasibility = (
                "NEGATIVE_NET_EDGE"
            )

        coverage = {
            field: (
                value is not None
            )
            for (
                field,
                value,
            ) in percent_values.items()
        }

        coverage[
            "gas_cost_usd"
        ] = gas_cost_usd is not None

        coverage[
            "trade_size_usd"
        ] = trade_size_usd is not None

        coverage[
            "expected_gross_edge_pct"
        ] = (
            expected_gross_edge_pct
            is not None
        )

        known_count = sum(
            bool(value)
            for (
                key,
                value,
            ) in coverage.items()
            if key
            != "expected_gross_edge_pct"
        )

        cost_input_count = 7

        cost_confidence = (
            known_count
            / cost_input_count
            * 100.0
        )

        return {
            "model": (
                "execution_cost_v1"
            ),

            "trade_size_usd": (
                trade_size_usd
            ),

            "components_pct": {
                **percent_values,
                "gas_cost_pct": (
                    gas_cost_pct
                ),
            },

            "gas_cost_usd": (
                gas_cost_usd
            ),

            "known_percent_cost_pct": (
                known_percent_cost
            ),

            "known_total_cost_pct": (
                known_total_cost_pct
            ),

            "break_even_edge_pct": (
                break_even_edge_pct
            ),

            "expected_gross_edge_pct": (
                expected_gross_edge_pct
            ),

            "net_edge_pct": (
                net_edge_pct
            ),

            "cost_complete": (
                cost_complete
            ),

            "cost_confidence": (
                cost_confidence
            ),

            "unknown_components": (
                unknown_components
            ),

            "coverage": coverage,

            "feasibility": (
                feasibility
            ),

            # Authority boundary.
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
