import requests

def get_pairs(token):

    url=f"https://api.dexscreener.com/token-pairs/v1/bsc/{token}"

    r=requests.get(url,timeout=15)

    r.raise_for_status()

    return r.json()


if __name__=="__main__":

    token=input("Token Address : ").strip()

    pairs=get_pairs(token)

    print()

    passed=0

    for p in pairs:

        dex=(p.get("dexId") or "").lower()

        liq=(p.get("liquidity") or {}).get("usd") or 0

        if dex!="pancakeswap":
            continue

        if liq<50000:
            continue

        passed+=1

        print("--------------------------------")
        print("DEX       :",dex)
        print("Pair      :",p.get("pairAddress"))
        print("Liquidity :",liq)
        print("Price USD :",p.get("priceUsd"))
        print("FDV       :",p.get("fdv"))
        print("MarketCap :",p.get("marketCap"))
        print("URL       :",p.get("url"))

    print()
    print("Geçen Aday Sayısı :",passed)
