#!/usr/bin/env python3
"""
Test script to directly call HyperLiquid and see positions.
"""
import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.config import settings
import ccxt.async_support as ccxt

async def test_positions():
    """Test HyperLiquid positions directly."""
    
    print(f"Wallet Address: {settings.HYPERLIQUID_WALLET_KEY}")
    print(f"Testnet: {settings.HYPERLIQUID_TESTNET}")
    
    # Create exchange instance
    exchange = ccxt.hyperliquid({
        'walletAddress': settings.HYPERLIQUID_WALLET_KEY,
        'privateKey': settings.HYPERLIQUID_PRIVATE_KEY,
        'options': {
            'testnet': settings.HYPERLIQUID_TESTNET,
        },
        'sandbox': settings.HYPERLIQUID_TESTNET
    })
    
    try:
        # Test positions with user parameter
        params = {'user': settings.HYPERLIQUID_WALLET_KEY}
        print(f"Fetching positions with params: {params}")
        
        positions = await exchange.fetch_positions(params=params)
        print(f"Total positions returned: {len(positions)}")
        
        for i, pos in enumerate(positions):
            print(f"Position {i+1}:")
            print(f"  Symbol: {pos.get('symbol')}")
            print(f"  Size: {pos.get('size')}")
            print(f"  Contracts: {pos.get('contracts')}")
            print(f"  Side: {pos.get('side')}")
            print(f"  Entry Price: {pos.get('entryPrice')}")
            print(f"  Mark Price: {pos.get('markPrice')}")
            print(f"  PNL: {pos.get('unrealizedPnl')}")
            print("  ---")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(test_positions())
