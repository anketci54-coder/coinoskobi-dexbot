from web3 import Web3

from app.chains.bsc import w3
from app.config.contracts import PANCAKE_ROUTER
from app.config.abis.router import ROUTER_ABI

router=w3.eth.contract(
    address=Web3.to_checksum_address(PANCAKE_ROUTER),
    abi=ROUTER_ABI
)
