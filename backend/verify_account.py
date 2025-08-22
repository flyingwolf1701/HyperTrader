#!/usr/bin/env python3
"""
Verify account authentication and get account information.
"""

import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.config import settings
import ccxt.async_support as ccxt

async def verify_account_info():
    """Verify account information and authentication."""
    
    wallet_address = settings.HYPERLIQUID_WALLET_KEY
    private_key = settings.HYPERLIQUID_PRIVATE_KEY
    
    print(f"Wallet Address: {wallet_address}")
    print(f"Private Key: {private_key[:10]}...{private_key[-10:]}")  # Partial display for security
    print(f"Testnet: {settings.HYPERLIQUID_TESTNET}")
    
    try:
        exchange = ccxt.hyperliquid({
            'walletAddress': wallet_address,
            'privateKey': private_key,
            'options': {
                'testnet': settings.HYPERLIQUID_TESTNET,
            },
            'sandbox': settings.HYPERLIQUID_TESTNET
        })
        
        print("\n=== Testing Account Access ===")
        
        # Test 1: Load markets (public endpoint)
        markets = await exchange.load_markets()
        print(f"✓ Markets loaded: {len(markets)} available")
        
        # Test 2: Check if we can access account-specific endpoints
        params = {'user': wallet_address}
        
        # Test balance endpoint
        try:
            balance = await exchange.fetch_balance(params=params)
            print(f"✓ Balance endpoint accessible")
            print(f"  Balance keys: {list(balance.keys())}")
            
            # Check for USDC specifically
            if 'USDC' in balance:
                usdc_info = balance['USDC']
                print(f"  USDC: free={usdc_info.get('free', 0)}, used={usdc_info.get('used', 0)}, total={usdc_info.get('total', 0)}")
        except Exception as e:
            print(f"✗ Balance endpoint failed: {e}")
        
        # Test positions endpoint  
        try:
            positions = await exchange.fetch_positions(params=params)
            print(f"✓ Positions endpoint accessible")
            print(f"  Raw positions count: {len(positions)}")
            
            # Show all positions (even zero size)
            for i, pos in enumerate(positions):
                if i < 10:  # Show first 10
                    symbol = pos.get('symbol', 'UNKNOWN')
                    size = pos.get('size', 0)
                    contracts = pos.get('contracts', 0)
                    side = pos.get('side', 'unknown')
                    print(f"    {symbol}: size={size}, contracts={contracts}, side={side}")
                elif i == 10:
                    print(f"    ... and {len(positions) - 10} more positions")
                    break
                    
        except Exception as e:
            print(f"✗ Positions endpoint failed: {e}")
        
        # Test orders endpoint
        try:
            orders = await exchange.fetch_open_orders(params=params)
            print(f"✓ Orders endpoint accessible")
            print(f"  Open orders count: {len(orders)}")
        except Exception as e:
            print(f"✗ Orders endpoint failed: {e}")
        
        # Test trades endpoint
        try:
            trades = await exchange.fetch_my_trades(params=params)
            print(f"✓ Trades endpoint accessible")
            print(f"  Recent trades count: {len(trades)}")
            
            if trades:
                print(f"  Most recent trade:")
                recent = trades[0]
                print(f"    {recent.get('symbol')} {recent.get('side')} {recent.get('amount')} @ {recent.get('price')}")
        except Exception as e:
            print(f"✗ Trades endpoint failed: {e}")
        
        await exchange.close()
        
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to initialize exchange: {e}")

if __name__ == "__main__":
    asyncio.run(verify_account_info())