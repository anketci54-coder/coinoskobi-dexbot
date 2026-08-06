import requests

URL = "https://api.dexscreener.com/token-profiles/latest/v1"

def latest_tokens():

    r = requests.get(URL, timeout=15)

    r.raise_for_status()

    return r.json()


if __name__ == "__main__":

    data = latest_tokens()

    print("Toplam Token:", len(data))
    print()

    for token in data[:20]:

        print("--------------------------------")
        print("Chain :", token.get("chainId"))
        print("Token :", token.get("tokenAddress"))
        print("URL   :", token.get("url"))
