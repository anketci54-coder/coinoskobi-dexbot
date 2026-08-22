from web3 import Web3

from app.chains.bsc import w3
from app.config.contracts import (
    PANCAKE_ROUTER,
    WBNB,
    USDT,
    BUSD,
)
from app.config.early_entry import (
    RESERVE_HISTORY_BLOCK_OFFSETS,
)


PAIR_ABI = [
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"type": "uint112"},
            {"type": "uint112"},
            {"type": "uint32"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


ERC20_ABI = [
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]


ROUTER_ABI = [
    {
        "inputs": [
            {
                "name": "amountIn",
                "type": "uint256",
            },
            {
                "name": "path",
                "type": "address[]",
            },
        ],
        "name": "getAmountsOut",
        "outputs": [
            {
                "type": "uint256[]",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def _wbnb_usd(router):
    one_wbnb = 10 ** 18

    for stable in (
        USDT,
        BUSD,
    ):
        try:
            path = [
                Web3.to_checksum_address(
                    WBNB
                ),
                Web3.to_checksum_address(
                    stable
                ),
            ]

            amounts = (
                router.functions
                .getAmountsOut(
                    one_wbnb,
                    path,
                )
                .call()
            )

            if (
                amounts
                and int(amounts[-1]) > 0
            ):
                return (
                    int(amounts[-1])
                    / 10 ** 18,
                    path[-1],
                )

        except Exception:
            continue

    return None, None


def analyze(token, pair):
    try:
        token_address = (
            Web3.to_checksum_address(
                token
            )
        )

        pair_address = (
            Web3.to_checksum_address(
                pair
            )
        )

        wbnb = Web3.to_checksum_address(
            WBNB
        )

        contract = w3.eth.contract(
            address=pair_address,
            abi=PAIR_ABI,
        )

        token0 = Web3.to_checksum_address(
            contract.functions.token0().call()
        )

        token1 = Web3.to_checksum_address(
            contract.functions.token1().call()
        )

        if {
            token0.lower(),
            token1.lower(),
        } != {
            token_address.lower(),
            wbnb.lower(),
        }:
            raise ValueError(
                "pair is not token/WBNB"
            )

        token_contract = w3.eth.contract(
            address=token_address,
            abi=ERC20_ABI,
        )

        decimals = int(
            token_contract.functions
            .decimals()
            .call()
        )

        router = w3.eth.contract(
            address=Web3.to_checksum_address(
                PANCAKE_ROUTER
            ),
            abi=ROUTER_ABI,
        )

        (
            wbnb_usd,
            stable_quote,
        ) = _wbnb_usd(
            router
        )

        latest_block = int(
            w3.eth.block_number
        )

        samples = []

        for offset in (
            RESERVE_HISTORY_BLOCK_OFFSETS
        ):
            block = max(
                0,
                latest_block - int(offset),
            )

            try:
                (
                    reserve0,
                    reserve1,
                    _,
                ) = (
                    contract.functions
                    .getReserves()
                    .call(
                        block_identifier=block
                    )
                )

            except Exception:
                continue

            if (
                token0.lower()
                == token_address.lower()
            ):
                token_raw = reserve0
                wbnb_raw = reserve1

            else:
                token_raw = reserve1
                wbnb_raw = reserve0

            token_reserve = (
                int(token_raw)
                / (10 ** decimals)
            )

            wbnb_reserve = (
                int(wbnb_raw)
                / 1e18
            )

            if (
                token_reserve <= 0
                or wbnb_reserve <= 0
            ):
                continue

            token_price_wbnb = (
                wbnb_reserve
                / token_reserve
            )

            token_price_usd = (
                token_price_wbnb
                * wbnb_usd
                if wbnb_usd is not None
                else None
            )

            samples.append({
                "block": block,

                "token_reserve": (
                    token_reserve
                ),

                "wbnb_reserve": (
                    wbnb_reserve
                ),

                "token_price_usd": (
                    token_price_usd
                ),
            })

        current = (
            samples[-1]
            if samples
            else None
        )

        quote_reserve_usd = (
            current["wbnb_reserve"]
            * wbnb_usd
            if (
                current
                and wbnb_usd is not None
            )
            else None
        )

        liquidity_usd = (
            2.0
            * quote_reserve_usd
            if quote_reserve_usd
            is not None
            else None
        )

        route_friction = None
        route_quote_out_wbnb = None

        if current:
            one_token_raw = (
                10 ** decimals
            )

            try:
                amounts = (
                    router.functions
                    .getAmountsOut(
                        one_token_raw,
                        [
                            token_address,
                            wbnb,
                        ],
                    )
                    .call()
                )

                route_quote_out_wbnb = (
                    int(amounts[-1])
                    / 1e18
                )

                spot_out_wbnb = (
                    current["wbnb_reserve"]
                    / current["token_reserve"]
                )

                if spot_out_wbnb > 0:
                    route_friction = max(
                        0.0,
                        min(
                            1.0,
                            (
                                1.0
                                - route_quote_out_wbnb
                                / spot_out_wbnb
                            ),
                        ),
                    )

            except Exception:
                pass

        price_series = [
            row["token_price_usd"]
            for row in samples
            if (
                row.get(
                    "token_price_usd"
                )
                is not None
            )
        ]

        reserve_change = None

        if (
            len(samples) >= 2
            and samples[0][
                "wbnb_reserve"
            ] > 0
        ):
            reserve_change = (
                samples[-1][
                    "wbnb_reserve"
                ]
                / samples[0][
                    "wbnb_reserve"
                ]
                - 1.0
            )

        return {
            "success": True,
            "source": (
                "exit_feasibility"
            ),
            "error": None,
            "data": {
                "pair": pair_address,

                "pair_membership_ok": True,

                "token_decimals": decimals,

                "wbnb_usd_estimate": (
                    wbnb_usd
                ),

                "stable_quote_token": (
                    stable_quote
                ),

                "quote_reserve_usd": (
                    quote_reserve_usd
                ),

                "liquidity_usd_estimate": (
                    liquidity_usd
                ),

                "reserve_change_fraction": (
                    reserve_change
                ),

                "reserve_samples": (
                    samples
                ),

                "spot_price_series_usd": (
                    price_series
                ),

                "route_quote_one_token_wbnb": (
                    route_quote_out_wbnb
                ),

                "route_friction_fraction": (
                    route_friction
                ),

                "gas_price_wei": int(
                    w3.eth.gas_price
                ),

                "evidence_complete": (
                    len(price_series) >= 2
                    and quote_reserve_usd
                    is not None
                    and quote_reserve_usd > 0
                ),

                "sellability_proof": False,

                "trade_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            },
        }

    except Exception as exc:
        return {
            "success": False,
            "source": (
                "exit_feasibility"
            ),
            "error": str(exc),
            "data": {
                "pair": pair,

                "pair_membership_ok": False,

                "evidence_complete": False,

                "spot_price_series_usd": [],

                "quote_reserve_usd": None,

                "trade_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            },
        }
