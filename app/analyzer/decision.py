import json

from app.analyzer.token import analyze as token_info
from app.analyzer.pair import analyze as pair_info
from app.risk.bytecode import analyze as risk_info

def decision(token):

    print()
    print("========================================")
    print(" Coinoskobi Decision Engine")
    print("========================================")

    info = token_info(token)

    print()
    print("ERC20")
    print(json.dumps(info, indent=4))

    print()
    print("PAIR")
    pair_info(token)

    print()
    print("BYTECODE RISK")
    risk_info(token)

    result = {
        "token": token,
        "name": info["name"],
        "symbol": info["symbol"],
        "decimals": info["decimals"],
        "supply": info["supply"],
        "status": "WATCH"
    }

    print()
    print("========================================")
    print("SUMMARY")
    print(json.dumps(result, indent=4))
    print("========================================")


if __name__=="__main__":

    token=input("Token : ").strip()

    decision(token)
