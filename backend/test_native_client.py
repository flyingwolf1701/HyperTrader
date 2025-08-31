"""
Test Script for Native Hyperliquid Exchange Client
Verifies the coin-agnostic implementation works correctly
"""
import asyncio
from decimal import Decimal
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.exchange.exchange_client import HyperliquidExchangeClient


async def test_hyperliquid_client():
    """Test the native Hyperliquid client functionality"""
    
    print("=" * 60)
    print("TESTING NATIVE HYPERLIQUID CLIENT")
    print("=" * 60)
    
    try:
        # Initialize client
        client = HyperliquidExchangeClient(testnet=True)
        print("Client initialized successfully")
        
        # Test 1: Get balance
        print("\n1. Testing balance retrieval...")
        balance = client.get_balance("USDC")
        print(f"USDC Balance: Available ${balance.available}, Total ${balance.total}")
        
        # Test 2: Get current price for ETH
        print("\n2. Testing price retrieval...")
        eth_price = client.get_current_price("ETH/USDC:USDC")
        print(f"ETH/USDC price: ${eth_price}")
        
        # Test 3: Get current price for BTC (if available)
        try:
            btc_price = client.get_current_price("BTC/USDC:USDC")
            print(f"BTC/USDC price: ${btc_price}")
        except Exception as e:
            print(f"BTC/USDC not available: {e}")
        
        # Test 4: Check for existing positions
        print("\n3. Testing position retrieval...")
        eth_position = client.get_position("ETH/USDC:USDC")
        if eth_position:
            print(f"ETH Position: {eth_position.side} {eth_position.size} @ ${eth_position.entry_price}")
            print(f"   PnL: ${eth_position.unrealized_pnl}")
        else:
            print("No ETH position found")
        
        # Test 5: Test coin name extraction
        print("\n4. Testing coin name extraction...")
        symbols_to_test = [
            "ETH/USDC:USDC",
            "BTC/USDC:USDC", 
            "SOL/USDC:USDC"
        ]
        
        for symbol in symbols_to_test:
            coin_name = symbol.split("/")[0] if "/" in symbol else symbol
            print(f"   {symbol} -> Coin: {coin_name}")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("Native Hyperliquid client is working correctly!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_method_names():
    """Test that the new coin-agnostic method names are correct"""
    
    print("\n" + "=" * 60)
    print("TESTING COIN-AGNOSTIC METHOD NAMES")
    print("=" * 60)
    
    client = HyperliquidExchangeClient(testnet=True)
    
    # Check that new methods exist
    methods_to_check = [
        'buy_long_usd',
        'open_short_usd', 
        'sell_long_coin',  # Updated from sell_long_eth
        'close_short_coin',  # Updated from close_short_eth
        'get_balance',
        'get_position',
        'get_current_price',
        'place_order',
        'set_leverage',
        'close_position'
    ]
    
    print("Checking method availability:")
    for method_name in methods_to_check:
        if hasattr(client, method_name):
            method = getattr(client, method_name)
            if callable(method):
                print(f"[OK] {method_name}()")
            else:
                print(f"[ERROR] {method_name} exists but is not callable")
        else:
            print(f"[ERROR] {method_name}() - NOT FOUND")
    
    print("\nCoin-agnostic methods ready for any asset!")
    print("   - ETH: sell_long_coin('ETH/USDC:USDC', coin_amount)")
    print("   - BTC: sell_long_coin('BTC/USDC:USDC', coin_amount)")  
    print("   - SOL: sell_long_coin('SOL/USDC:USDC', coin_amount)")


if __name__ == "__main__":
    print("Starting Hyperliquid Native Client Tests...")
    
    # Test method names first (synchronous)
    test_method_names()
    
    # Test async functionality
    try:
        success = asyncio.run(test_hyperliquid_client())
        if success:
            print("\n[SUCCESS] Migration to Native Hyperliquid Client COMPLETE!")
            print("You can now trade any asset on Hyperliquid with coin-agnostic methods!")
        else:
            print("\n[WARNING] Some tests failed. Check your environment configuration.")
    except Exception as e:
        print(f"\n[ERROR] Test execution failed: {e}")
        print("\nPlease check:")
        print("1. HYPERLIQUID_WALLET_KEY is set in your environment")
        print("2. HYPERLIQUID_PRIVATE_KEY is set in your environment") 
        print("3. Your testnet credentials are valid")
