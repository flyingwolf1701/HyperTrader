import requests
import json

# Get all markets
response = requests.get("http://localhost:3000/api/v1/exchange/pairs")
markets = response.json()

# Search for LINK
link_markets = []
for market in markets:
    if 'LINK' in market['symbol'].upper():
        link_markets.append(market)

print("LINK markets found:")
for market in link_markets:
    print(f"- {market['symbol']}")

# Also search for common patterns
print("\nSearching for common patterns:")
patterns = ['BTC', 'ETH', 'SOL', 'USDC', 'USDT']
for pattern in patterns:
    found = [m['symbol'] for m in markets if pattern in m['symbol']]
    if found:
        print(f"{pattern} markets: {found[:5]}...")  # Show first 5