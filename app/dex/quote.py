from web3 import Web3

from app.dex.pancake import router

def quote(amount_in,token_in,token_out):

    amounts=router.functions.getAmountsOut(
        amount_in,
        [
            Web3.to_checksum_address(token_in),
            Web3.to_checksum_address(token_out)
        ]
    ).call()

    return amounts[-1]
