from eth_account import Account
from web3 import Web3

from app.config.settings import PRIVATE_KEY
from app.chains.bsc import w3


def load_account():
    if not PRIVATE_KEY:
        return None

    return Account.from_key(PRIVATE_KEY)


def wallet_address():
    account = load_account()

    if account is None:
        return None

    return Web3.to_checksum_address(account.address)


def bnb_balance():
    address = wallet_address()

    if address is None:
        return None

    balance = w3.eth.get_balance(address)

    return w3.from_wei(balance, "ether")
