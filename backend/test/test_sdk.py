from hyperliquid_sdk import HyperliquidSDK

# Replace with your actual API key and secret for testing
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"

def main():
    sdk = HyperliquidSDK(api_key=API_KEY, api_secret=API_SECRET)

    # --- Test get_balance ---
    print("--- Testing get_balance ---")
    balance = sdk.get_balance()
    print(f"Available balance: {balance} USDC")
    print("-" * 20)

    # --- Test place_market_order (example: buy 0.1 ETH) ---
    print("--- Testing place_market_order ---")
    symbol = "ETH"
    side = "buy"
    amount = 0.1
    order_confirmation = sdk.place_market_order(symbol, side, amount)
    print(f"Market order confirmation: {order_confirmation}")
    print("-" * 20)
    
    # --- Test get_position ---
    print("--- Testing get_position ---")
    position = sdk.get_position(symbol)
    if position:
        print(f"Current position for {symbol}:")
        print(f"  Size: {position['size']}")
        print(f"  Entry Price: {position['entry_price']}")
        print(f"  Side: {position['side']}")
        print(f"  Unrealized PNL: {position['unrealized_pnl']}")
    else:
        print(f"No open position for {symbol}.")
    print("-" * 20)

    # --- Test close_position ---
    print("--- Testing close_position ---")
    close_confirmation = sdk.close_position(symbol)
    print(f"Close position confirmation: {close_confirmation}")
    print("-" * 20)

if __name__ == "__main__":
    main()
    