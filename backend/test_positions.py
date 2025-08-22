#!/usr/bin/env python3
"""
Test script to verify position and trade fetching functionality.
"""

import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.logging import configure_logging
from app.services.exchange import exchange_manager
from app.core.config import settings
from loguru import logger

async def test_position_fetching():
    """Test all position and trade fetching functionality."""
    
    print("Setting up logging...")
    configure_logging()
    
    print("Initializing exchange manager...")
    try:
        await exchange_manager.initialize()
        print(f"Connected to HyperLiquid (Testnet: {settings.HYPERLIQUID_TESTNET})")
    except Exception as e:
        print(f"Failed to initialize exchange: {e}")
        return
    
    try:
        print("\n=== Testing Position Fetching ===")
        
        # Test 1: Fetch all positions
        print("\n1. Fetching all positions...")
        positions = await exchange_manager.fetch_positions()
        print(f"Found {len(positions)} open positions:")
        for pos in positions:
            print(f"  - {pos.symbol}: {pos.side} {pos.size} "
                  f"(Entry: ${pos.entry_price}, Mark: ${pos.mark_price}, "
                  f"PnL: ${pos.pnl})")
        
        # Test 2: Get position summary
        print("\n2. Getting position summary...")
        summary = await exchange_manager.get_position_summary()
        print(f"Position Summary:")
        print(f"  - Total positions: {summary['total_positions']}")
        print(f"  - Long positions: {summary['long_positions']}")
        print(f"  - Short positions: {summary['short_positions']}")
        print(f"  - Total unrealized PnL: ${summary['total_unrealized_pnl']:.2f}")
        print(f"  - Total notional value: ${summary['total_notional_value']:.2f}")
        
        # Test 3: Fetch open orders
        print("\n3. Fetching open orders...")
        orders = await exchange_manager.fetch_open_orders()
        print(f"Found {len(orders)} open orders:")
        for order in orders:
            print(f"  - {order.symbol}: {order.side} {order.type} "
                  f"{order.amount} @ ${order.price if order.price else 'market'} "
                  f"(Status: {order.status}, Filled: {order.filled})")
        
        # Test 4: Fetch recent trades
        print("\n4. Fetching recent trades...")
        trades = await exchange_manager.fetch_my_trades(limit=10)
        print(f"Found {len(trades)} recent trades:")
        for trade in trades:
            print(f"  - {trade.symbol}: {trade.side} {trade.amount} @ ${trade.price} "
                  f"(Cost: ${trade.cost}, Fee: ${trade.fee if trade.fee else 'N/A'})")
        
        # Test 5: Fetch account balances
        print("\n5. Fetching account balances...")
        balances = await exchange_manager.fetch_all_balances()
        print("Account Balances:")
        for currency, amount in balances.items():
            if float(amount) > 0:
                print(f"  - {currency}: {amount}")
        
        print("\n=== Position Fetching Test Complete ===")
        
    except Exception as e:
        logger.error(f"Error during position testing: {e}", exc_info=True)
        print(f"Test failed: {e}")
    
    finally:
        print("\nClosing exchange connection...")
        await exchange_manager.close()

if __name__ == "__main__":
    asyncio.run(test_position_fetching())