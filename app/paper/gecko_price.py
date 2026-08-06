import requests

class GeckoPrice:

    URL = "https://api.geckoterminal.com/api/v2/networks/bsc/tokens/{}"

    def get_price(self, token):

        r = requests.get(
            self.URL.format(token),
            headers={
                "Accept":"application/json;version=20230302"
            },
            timeout=15
        )

        r.raise_for_status()

        data = r.json()["data"]["attributes"]

        return float(data["price_usd"])
