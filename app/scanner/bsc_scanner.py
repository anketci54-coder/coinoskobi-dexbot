import requests

URL = "https://api.dexscreener.com/token-profiles/latest/v1"

def latest_bsc():
    r = requests.get(URL, timeout=15)
    r.raise_for_status()

    result = []

    for token in r.json():
        if token.get("chainId") == "bsc":
            result.append(token)

    return result


if __name__ == "__main__":

    tokens = latest_bsc()

    print()
    print("BSC Token Sayısı :", len(tokens))
    print()

    for t in tokens:

        print("--------------------------------")
        print("Address :", t.get("tokenAddress"))
        print("URL     :", t.get("url"))
