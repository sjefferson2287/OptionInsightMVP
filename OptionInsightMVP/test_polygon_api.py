from src.polygon_api import get_option_chain_snapshot, get_btc_price

# Test BTC Price
btc_price = get_btc_price()
print("BTC/USD:", btc_price)

# Test Option Chain Snapshot for MARA
snapshot = get_option_chain_snapshot("MARA")

if snapshot:
    print("First Option Contract:")
    print(snapshot[0])
else:
    print("No option data returned.")
