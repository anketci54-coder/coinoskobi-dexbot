from app.scanner.pairs import latest_pairs

pairs=latest_pairs()

print()

print("Yeni Pair Sayısı:",len(pairs))

print()

for p in pairs[-20:]:

    print("--------------------------------")
    print("Block :",p["block"])
    print("Pair  :",p["pair"])
    print("Token0:",p["token0"])
    print("Token1:",p["token1"])
    print("TX    :",p["tx"])
