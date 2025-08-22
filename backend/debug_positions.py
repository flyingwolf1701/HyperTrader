#!/usr/bin/env python3
"""
Debug script to test HyperLiquid position fetching directly.
"""

import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.config import settings
import ccxt.async_support as ccxt

async def debug_hyperliquid():
    """Test HyperLiquid position fetching directly."""
    
    print(f"Wallet Address: {settings.HYPERLIQUID_WALLET_KEY[:10]}...")
    print(f"Private Key: {'*' * 10}")
    print(f"Testnet: {settings.HYPERLIQUID_TESTNET}")
    
    exchange = ccxt.hyperliquid({
        'walletAddress': settings.HYPERLIQUID_WALLET_KEY,
        'privateKey': settings.HYPERLIQUID_PRIVATE_KEY,
        'options': {
            'testnet': settings.HYPERLIQUID_TESTNET,
        },
        'sandbox': settings.HYPERLIQUID_TESTNET
    })
    
    try:
        print("\nTesting different approaches to fetch positions...")
        
        # Approach 1: Default call
        print("\n1. Default call:")
        try:
            positions = await exchange.fetch_positions()
            print(f"Success: {len(positions)} positions")
        except Exception as e:
            print(f"Failed: {e}")
        
        # Approach 2: With user parameter
        print("\n2. With user parameter:")
        try:
            positions = await exchange.fetch_positions(params={'user': settings.HYPERLIQUID_WALLET_KEY})
            print(f"Success: {len(positions)} positions")
        except Exception as e:
            print(f"Failed: {e}")
        
        # Approach 3: With empty symbols list
        print("\n3. With empty symbols list:")
        try:
            positions = await exchange.fetch_positions([])
            print(f"Success: {len(positions)} positions")
        except Exception as e:
            print(f"Failed: {e}")
        
        # Approach 4: With specific symbol
        print("\n4. With specific symbol:")
        try:
            positions = await exchange.fetch_positions(['BTC/USDC:USDC'])
            print(f"Success: {len(positions)} positions")
        except Exception as e:
            print(f"Failed: {e}")
        
        # Test balance fetching
        print("\n5. Test balance fetching:")
        try:
            balance = await exchange.fetch_balance()
            print(f"Success: Balance keys: {list(balance.keys())}")
        except Exception as e:
            print(f"Failed: {e}")
            
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(debug_hyperliquid())