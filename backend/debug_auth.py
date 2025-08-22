#!/usr/bin/env python3
"""
Debug script to test HyperLiquid authentication approaches.
"""

import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.config import settings
import ccxt.async_support as ccxt

async def debug_hyperliquid_auth():
    """Test different HyperLiquid authentication approaches."""
    
    print(f"Wallet Address: {settings.HYPERLIQUID_WALLET_KEY}")
    print(f"Testnet: {settings.HYPERLIQUID_TESTNET}")
    
    # Test different configurations
    configs_to_test = [
        {
            'name': 'Current config with walletAddress',
            'config': {
                'walletAddress': settings.HYPERLIQUID_WALLET_KEY,
                'privateKey': settings.HYPERLIQUID_PRIVATE_KEY,
                'options': {
                    'testnet': settings.HYPERLIQUID_TESTNET,
                },
                'sandbox': settings.HYPERLIQUID_TESTNET
            }
        },
        {
            'name': 'Config with apiKey instead of walletAddress',
            'config': {
                'apiKey': settings.HYPERLIQUID_WALLET_KEY,
                'secret': settings.HYPERLIQUID_PRIVATE_KEY,
                'options': {
                    'testnet': settings.HYPERLIQUID_TESTNET,
                },
                'sandbox': settings.HYPERLIQUID_TESTNET
            }
        },
        {
            'name': 'Config with user in options',
            'config': {
                'walletAddress': settings.HYPERLIQUID_WALLET_KEY,
                'privateKey': settings.HYPERLIQUID_PRIVATE_KEY,
                'options': {
                    'testnet': settings.HYPERLIQUID_TESTNET,
                    'user': settings.HYPERLIQUID_WALLET_KEY,
                },
                'sandbox': settings.HYPERLIQUID_TESTNET
            }
        }
    ]
    
    for test_config in configs_to_test:
        print(f"\n=== Testing: {test_config['name']} ===")
        
        try:
            exchange = ccxt.hyperliquid(test_config['config'])
            
            # Test 1: Check if markets work (doesn't require auth)
            print("Testing market data fetch...")
            markets = await exchange.load_markets()
            print(f"SUCCESS: Markets loaded: {len(markets)} available")
            
            # Test 2: Test positions with different user parameter approaches
            user_params_to_test = [
                {'user': settings.HYPERLIQUID_WALLET_KEY},
                {'user': settings.HYPERLIQUID_WALLET_KEY.lower()},
                {'address': settings.HYPERLIQUID_WALLET_KEY},
                {'walletAddress': settings.HYPERLIQUID_WALLET_KEY},
                {}  # No params
            ]
            
            for i, params in enumerate(user_params_to_test):
                try:
                    print(f"  Testing positions with params {i+1}: {params}")
                    positions = await exchange.fetch_positions(params=params)
                    print(f"  SUCCESS: Positions fetched: {len(positions)} positions")
                    if positions:
                        print(f"    First position: {positions[0]}")
                        break  # Found working params
                except Exception as e:
                    print(f"  FAILED: {str(e)[:100]}...")
            
            # Test 3: Test balance 
            for i, params in enumerate(user_params_to_test):
                try:
                    print(f"  Testing balance with params {i+1}: {params}")
                    balance = await exchange.fetch_balance(params=params)
                    print(f"  SUCCESS: Balance fetched: {list(balance.keys())}")
                    if balance.get('total'):
                        non_zero = {k: v for k, v in balance['total'].items() if float(v or 0) > 0}
                        print(f"    Non-zero balances: {non_zero}")
                        break
                except Exception as e:
                    print(f"  FAILED: {str(e)[:100]}...")
            
            await exchange.close()
            
        except Exception as e:
            print(f"FAILED Config: {e}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(debug_hyperliquid_auth())