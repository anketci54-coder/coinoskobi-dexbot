def analyze(address):
    return {
        "success": True,
        "source": "token",
        "data": {},
    }


if __name__ == "__main__":
    token = input("Token : ").strip()
    print(analyze(token))
