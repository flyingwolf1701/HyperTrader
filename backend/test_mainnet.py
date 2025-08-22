#!/usr/bin/env python3
"""
Quick test to check if positions are on mainnet vs testnet.
IMPORTANT: This script only fetches data, no trading operations.
"""

import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.config import settings
import ccxt.async_support as ccxt

async def test_mainnet_vs_testnet():
    """Test if positions exist on mainnet vs testnet."""
    
    wallet_address = settings.HYPERLIQUID_WALLET_KEY
    private_key = settings.HYPERLIQUID_PRIVATE_KEY
    
    print(f"Testing wallet: {wallet_address}")
    print(f"Current config testnet setting: {settings.HYPERLIQUID_TESTNET}")
    
    configs = [
        {"name": "TESTNET", "testnet": True},
        {"name": "MAINNET", "testnet": False}
    ]
    
    for config in configs:
        print(f"\n=== Testing {config['name']} ===")
        
        try:
            exchange = ccxt.hyperliquid({
                'walletAddress': wallet_address,
                'privateKey': private_key,
                'options': {
                    'testnet': config['testnet'],
                },
                'sandbox': config['testnet']
            })
            
            # Test positions
            params = {'user': wallet_address}
            positions = await exchange.fetch_positions(params=params)
            print(f"Positions found: {len(positions)}")
            
            if positions:
                print("POSITIONS FOUND:")
                for pos in positions:
                    if pos.get('contracts', 0) != 0 or pos.get('size', 0) != 0:
                        print(f"  {pos['symbol']}: {pos.get('size', 0)} size, {pos.get('contracts', 0)} contracts")
            
            # Test balance
            balance = await exchange.fetch_balance(params=params)
            total_balance = balance.get('total', {})
            non_zero = {k: v for k, v in total_balance.items() if float(v or 0) > 0}
            print(f"Non-zero balances: {non_zero}")
            
            await exchange.close()
            
        except Exception as e:
            print(f"ERROR on {config['name']}: {e}")

if __name__ == "__main__":
    asyncio.run(test_mainnet_vs_testnet())