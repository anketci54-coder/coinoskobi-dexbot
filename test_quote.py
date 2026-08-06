from web3 import Web3

from app.config.tokens import WBNB,USDT
from app.dex.quote import quote

amount=Web3.to_wei(1,"ether")

result=quote(amount,WBNB,USDT)

print("----------------------------")
print("1 WBNB")
print("=")
print(result/1e18,"USDT")
print("----------------------------")
