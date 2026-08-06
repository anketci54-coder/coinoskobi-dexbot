from web3 import Web3
from app.config.settings import RPC_URL

w3 = Web3(Web3.HTTPProvider(RPC_URL))

def connect():
    return w3.is_connected()

def chain_id():
    return w3.eth.chain_id

def latest_block():
    return w3.eth.block_number
