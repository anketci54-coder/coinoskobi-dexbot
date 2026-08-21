from web3 import Web3

from app.chains.bsc import w3
from app.config.early_entry import (
    LP_LOCKER_ADDRESSES,
    PANCAKE_V2_MINIMUM_LIQUIDITY,
)


ZERO_ADDRESS = (
    "0x0000000000000000000000000000000000000000"
)

DEAD_ADDRESS = (
    "0x000000000000000000000000000000000000dEaD"
)


PAIR_ABI = [
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {
                "name": "account",
                "type": "address",
            }
        ],
        "name": "balanceOf",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def analyze(pair):
    try:
        pair_address = Web3.to_checksum_address(
            pair
        )

        contract = w3.eth.contract(
            address=pair_address,
            abi=PAIR_ABI,
        )

        total_supply = int(
            contract.functions.totalSupply().call()
        )

        zero_balance = int(
            contract.functions.balanceOf(
                Web3.to_checksum_address(
                    ZERO_ADDRESS
                )
            ).call()
        )

        dead_balance = int(
            contract.functions.balanceOf(
                Web3.to_checksum_address(
                    DEAD_ADDRESS
                )
            ).call()
        )

        protocol_minimum = min(
            zero_balance,
            PANCAKE_V2_MINIMUM_LIQUIDITY,
        )

        effective_zero_burn = max(
            0,
            zero_balance - protocol_minimum,
        )

        locked_raw = 0
        checked = []
        holding = []

        seen = {
            ZERO_ADDRESS.lower(),
            DEAD_ADDRESS.lower(),
        }

        for raw_address in LP_LOCKER_ADDRESSES:
            address = Web3.to_checksum_address(
                raw_address
            )

            key = address.lower()

            if key in seen:
                continue

            seen.add(key)
            checked.append(address)

            balance = int(
                contract.functions.balanceOf(
                    address
                ).call()
            )

            if balance > 0:
                holding.append(address)
                locked_raw += balance

        if total_supply > 0:
            protected_raw = min(
                total_supply,
                (
                    effective_zero_burn
                    + dead_balance
                    + locked_raw
                ),
            )

            protected_fraction = (
                protected_raw
                / total_supply
            )

            withdrawable_fraction = (
                1.0
                - protected_fraction
            )

        else:
            protected_raw = 0
            protected_fraction = None
            withdrawable_fraction = None

        if total_supply <= 0:
            state = "NO_LP_SUPPLY"

        elif protected_raw > 0:
            state = (
                "PROTECTION_EVIDENCE_PRESENT"
            )

        else:
            state = "UNPROVEN"

        return {
            "success": True,
            "source": "lp_security",
            "error": None,
            "data": {
                "pair": pair_address,
                "state": state,
                "protection_evidence_present": (
                    protected_raw > 0
                ),
                # Evidence presence is not an
                # economic-safety decision.
                "economic_safety_authority": False,

                "total_supply_raw": (
                    total_supply
                ),

                "zero_address_balance_raw": (
                    zero_balance
                ),

                "protocol_minimum_liquidity_raw": (
                    protocol_minimum
                ),

                "effective_zero_burn_raw": (
                    effective_zero_burn
                ),

                "dead_address_burn_raw": (
                    dead_balance
                ),

                "verified_locker_raw": (
                    locked_raw
                ),

                "verified_protected_raw": (
                    protected_raw
                ),

                "lp_protected_fraction": (
                    protected_fraction
                ),

                "lp_withdrawable_fraction": (
                    withdrawable_fraction
                ),

                "locker_addresses_checked": (
                    checked
                ),

                "locker_addresses_holding_lp": (
                    holding
                ),

                "formula": (
                    "(zero_balance-protocol_minimum)"
                    "+dead_balance"
                    "+verified_locker_balance"
                ),

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
            "source": "lp_security",
            "error": str(exc),
            "data": {
                "pair": pair,
                "state": "UNKNOWN",

                "lp_protected_fraction": None,
                "lp_withdrawable_fraction": None,

                "trade_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            },
        }
