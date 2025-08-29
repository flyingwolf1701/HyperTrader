"""Quick script to check actual positions on testnet"""

from src.exchange.exchange_client import HyperliquidExchangeClient

def check_positions():
    client = HyperliquidExchangeClient(testnet=True)
    
    symbol = "ETH/USDC:USDC"
    
    print("Checking positions for:", symbol)
    print("-" * 50)
    
    # Get raw positions
    positions = client.exchange.fetch_positions([symbol])
    
    print(f"Raw positions response ({len(positions)} items):")
    for i, pos in enumerate(positions):
        print(f"\nPosition {i+1}:")
        print(f"  Symbol: {pos.get('symbol')}")
        print(f"  Side: {pos.get('side')}")
        print(f"  Contracts: {pos.get('contracts')}")
        print(f"  Percentage: {pos.get('percentage')}")
        print(f"  Info: {pos.get('info')}")
        
    print("\n" + "-" * 50)
    
    # Check what get_position returns
    position = client.get_position(symbol)
    
    if position:
        print("get_position() returned:")
        print(f"  Side: {position['side']}")
        print(f"  Contracts: {position.get('contracts')}")
        print(f"  Entry Price: {position.get('entry_price')}")
        print(f"  PnL: {position.get('pnl')}")
    else:
        print("get_position() returned: None (no position)")

if __name__ == "__main__":
    check_positions()
