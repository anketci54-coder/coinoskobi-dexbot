import sqlite3
import requests

URL = "https://api.geckoterminal.com/api/v2/networks/bsc/new_pools"

r = requests.get(
    URL,
    headers={"Accept": "application/json;version=20230302"},
    timeout=20,
)

r.raise_for_status()

rows = r.json()["data"]

db = sqlite3.connect("data/cache/cache.db")

for item in rows:

    a = item["attributes"]

    db.execute(
        """
        INSERT OR REPLACE INTO gecko_pool_cache(

            pool,
            token,
            name,
            dex,
            liquidity,
            volume24,
            buys24,
            fdv,
            created_at,
            updated_at,
            price_usd

        )

        VALUES(

            ?,?,?,?,?,?,?,?,?,?,?

        )
        """,
        (
            a["address"],
            item["relationships"]["base_token"]["data"]["id"],
            a["name"],
            item["relationships"]["dex"]["data"]["id"],
            float(a["reserve_in_usd"] or 0),
            float(a["volume_usd"]["h24"] or 0),
            int(a["transactions"]["h24"]["buys"] or 0),
            float(a["fdv_usd"] or 0),
            a["pool_created_at"],
            __import__("datetime").datetime.utcnow().isoformat(timespec="seconds"),
            float(a["base_token_price_usd"] or 0),
        ),
    )

db.commit()

print("Pool :", len(rows))

print(
    "price örnek :",
    db.execute(
        "SELECT price_usd FROM gecko_pool_cache LIMIT 5"
    ).fetchall(),
)

db.close()
