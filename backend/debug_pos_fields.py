#!/usr/bin/env python3
"""
Debug position field values.
"""
import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.config import settings
import ccxt.async_support as ccxt

async def debug_position_fields():
    """Debug all position fields."""
    
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
        positions = await exchange.fetch_positions(params=params)
        print(f"Total positions returned: {len(positions)}")
        
        if positions:
            pos = positions[0]  # Look at first position in detail
            print(f"\nFirst position full data:")
            for key, value in pos.items():
                print(f"  {key}: {value} (type: {type(value).__name__})")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(debug_position_fields())
