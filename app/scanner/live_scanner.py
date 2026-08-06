import time
from web3 import Web3

from app.chains.bsc import w3
from app.config.factory import PANCAKE_FACTORY
from app.config.abis.factory import FACTORY_ABI

factory = w3.eth.contract(
    address=Web3.to_checksum_address(PANCAKE_FACTORY),
    abi=FACTORY_ABI
)

last_block = w3.eth.block_number

print(f"Scanner başladı. Blok: {last_block}")

while True:
    try:
        current = w3.eth.block_number

        while last_block < current:
            last_block += 1

            try:
                events = factory.events.PairCreated.get_logs(
                    from_block=last_block,
                    to_block=last_block
                )

                for e in events:
                    print("")
                    print("========== YENİ PAIR ==========")
                    print("Block :", e.blockNumber)
                    print("Pair  :", e.args.pair)
                    print("Token0:", e.args.token0)
                    print("Token1:", e.args.token1)
                    print("===============================")

            except Exception as err:
                print(f"Blok {last_block}: {err}")

        time.sleep(2)

    except KeyboardInterrupt:
        print("Scanner durduruldu.")
        break
