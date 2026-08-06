from web3 import Web3

from app.chains.bsc import w3
from app.config.factory import PANCAKE_FACTORY
from app.config.abis.factory_full import FACTORY_ABI
from app.config.abis.pair import PAIR_ABI
from app.config.tokens import WBNB

factory=w3.eth.contract(
    address=Web3.to_checksum_address(PANCAKE_FACTORY),
    abi=FACTORY_ABI
)

def analyze(token):

    pair=factory.functions.getPair(
        Web3.to_checksum_address(token),
        Web3.to_checksum_address(WBNB)
    ).call()

    if pair=="0x0000000000000000000000000000000000000000":
        print("WBNB Pair bulunamadı.")
        return

    print()
    print("Pair :",pair)

    contract=w3.eth.contract(
        address=Web3.to_checksum_address(pair),
        abi=PAIR_ABI
    )

    print("Token0 :",contract.functions.token0().call())
    print("Token1 :",contract.functions.token1().call())

    reserves=contract.functions.getReserves().call()

    print()
    print("Reserve0 :",reserves[0])
    print("Reserve1 :",reserves[1])

if __name__=="__main__":

    token=input("Token : ").strip()

    analyze(token)
