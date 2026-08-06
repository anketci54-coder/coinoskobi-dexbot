from dotenv import load_dotenv
import os
from web3 import Web3

load_dotenv(".env")

rpc = os.getenv("RPC_URL")

print("RPC =", rpc)

w3 = Web3(Web3.HTTPProvider(rpc))

print("Connected =", w3.is_connected())

if w3.is_connected():
    print("Chain ID =", w3.eth.chain_id)
    print("Latest Block =", w3.eth.block_number)
