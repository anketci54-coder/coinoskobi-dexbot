import os

from dotenv import load_dotenv
from web3 import Web3


load_dotenv(".env")


class RPCManager:

    def __init__(self):

        self.rpc = os.getenv("RPC_URL")

        if not self.rpc:
            raise RuntimeError("RPC_URL bulunamadı")

        self.w3 = Web3(Web3.HTTPProvider(self.rpc))

    def get_web3(self):

        return self.w3

    def connected(self):

        return self.w3.is_connected()

    def chain_id(self):

        return self.w3.eth.chain_id

    def latest_block(self):

        return self.w3.eth.block_number


rpc = RPCManager()
