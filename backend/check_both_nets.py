#!/usr/bin/env python3
"""
Check positions on both testnet and mainnet.
"""
import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.config import settings
import ccxt.async_support as ccxt

async def check_positions(testnet=True):
    """Check positions on testnet or mainnet."""
    
    network = "TESTNET" if testnet else "MAINNET"
    print(f"\n=== Checking {network} ===")
    print(f"Wallet Address: {settings.HYPERLIQUID_WALLET_KEY}")
    
    # Create exchange instance
    exchange = ccxt.hyperliquid({
        'walletAddress': settings.HYPERLIQUID_WALLET_KEY,
        'privateKey': settings.HYPERLIQUID_PRIVATE_KEY,
        'options': {
            'testnet': testnet,
        },
        'sandbox': testnet
    })
    
    try:
        # Test positions with user parameter
        params = {'user': settings.HYPERLIQUID_WALLET_KEY}
        positions = await exchange.fetch_positions(params=params)
        print(f"Total positions returned: {len(positions)}")
        
        if positions:
            for i, pos in enumerate(positions):
                print(f"Position {i+1}: {pos.get('symbol')} | Size: {pos.get('size')} | Side: {pos.get('side')}")
        else:
            print("No positions found")
            
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        await exchange.close()

async def main():
    # Check testnet
    await check_positions(testnet=True)
    
    # Check mainnet
    await check_positions(testnet=False)

if __name__ == "__main__":
    asyncio.run(main())
