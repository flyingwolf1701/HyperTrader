#!/usr/bin/env python3
"""
Test script to isolate and test stop limit buy order placement
This will help debug why limit buy orders aren't being placed
"""

import asyncio
import sys
import os
from decimal import Decimal
from pathlib import Path
import argparse
from loguru import logger
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from exchange.hyperliquid_sdk import HyperliquidClient


async def test_stop_limit_buy(symbol: str = "BTC", test_size: float = 0.001, price_offset: float = 100.0, use_testnet: bool = True):
    """
    Test placing a stop limit buy order above current market price
    
    Args:
        symbol: Trading symbol (e.g., "BTC")
        test_size: Size to test with (e.g., 0.001 BTC)
        price_offset: How much above market to place order (e.g., $100)
        use_testnet: Whether to use testnet
    """
    # Initialize
    load_dotenv()
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    logger.info(f"Testing stop limit buy for {symbol}")
    logger.info(f"Test size: {test_size} {symbol}")
    logger.info(f"Price offset: ${price_offset} above market")
    logger.info(f"Network: {'TESTNET' if use_testnet else 'MAINNET'}")
    
    # Initialize SDK client
    client = HyperliquidClient(use_testnet=use_testnet)
    
    # Get current market price
    current_price = client.get_current_price(symbol)
    logger.info(f"Current market price: ${current_price:.2f}")
    
    # Calculate trigger price (above market)
    trigger_price = current_price + Decimal(str(price_offset))
    limit_price = trigger_price  # Use same price for limit
    
    logger.warning(f"🎯 Will place STOP LIMIT BUY at ${trigger_price:.2f} (${price_offset} above market)")
    
    # Test 1: Try placing a regular limit buy above market (should fail or execute immediately)
    logger.info("\n" + "="*50)
    logger.info("TEST 1: Regular limit buy above market (should fail or execute)")
    logger.info("="*50)
    
    result = client.place_limit_order(
        symbol=symbol,
        is_buy=True,
        price=trigger_price,
        size=Decimal(str(test_size)),
        reduce_only=False,
        post_only=True  # This should cause rejection if price is above market
    )
    
    if result.success:
        logger.warning(f"✅ Regular limit buy placed: Order ID {result.order_id}")
        logger.warning("⚠️ This shouldn't work for orders above market with post_only=True!")
    else:
        logger.info(f"❌ Regular limit buy rejected (expected): {result.error_message}")
    
    # Wait a bit
    await asyncio.sleep(2)
    
    # Test 2: Try our new stop limit buy function
    logger.info("\n" + "="*50)
    logger.info("TEST 2: Stop limit buy (should place and wait)")
    logger.info("="*50)
    
    result = client.place_stop_limit_buy(
        symbol=symbol,
        size=Decimal(str(test_size)),
        trigger_price=trigger_price,
        limit_price=limit_price,
        reduce_only=False
    )
    
    if result.success:
        logger.warning(f"✅ STOP LIMIT BUY PLACED: Order ID {result.order_id}")
        logger.info(f"   Trigger: ${trigger_price:.2f}")
        logger.info(f"   Limit: ${limit_price:.2f}")
        logger.info("   This order should wait for price to rise before activating")
        
        # Get open orders to verify
        await asyncio.sleep(2)
        orders = client.get_open_orders(symbol)
        logger.info(f"\nOpen orders for {symbol}: {len(orders)}")
        for order in orders:
            logger.info(f"   Order: {order}")
            
    else:
        logger.error(f"❌ Stop limit buy FAILED: {result.error_message}")
        
    # Test 3: Try with different variations
    logger.info("\n" + "="*50)
    logger.info("TEST 3: Stop limit buy with lower limit price")
    logger.info("="*50)
    
    # Trigger above market, but limit at market (should fill when triggered)
    trigger_price2 = current_price + Decimal(str(price_offset * 2))
    limit_price2 = current_price
    
    logger.info(f"Trigger @ ${trigger_price2:.2f}, Limit @ ${limit_price2:.2f}")
    
    result = client.place_stop_limit_buy(
        symbol=symbol,
        size=Decimal(str(test_size)),
        trigger_price=trigger_price2,
        limit_price=limit_price2,
        reduce_only=False
    )
    
    if result.success:
        logger.warning(f"✅ STOP LIMIT BUY PLACED: Order ID {result.order_id}")
    else:
        logger.error(f"❌ Stop limit buy FAILED: {result.error_message}")
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("TEST COMPLETE")
    logger.info("="*50)
    logger.info("Check your Hyperliquid interface to see if orders appear")
    logger.info("Look for orders with 'TP/SL' indicator")
    
    # Show all open orders
    await asyncio.sleep(2)
    orders = client.get_open_orders(symbol)
    logger.info(f"\nFinal open orders count: {len(orders)}")
    
    # Optionally cancel test orders
    if orders and input("\nCancel test orders? (y/n): ").lower() == 'y':
        for order in orders:
            if hasattr(order, 'order_id'):
                client.cancel_order(symbol, order.order_id)
                logger.info(f"Cancelled order {order.order_id}")


async def main():
    parser = argparse.ArgumentParser(description='Test stop limit buy orders')
    parser.add_argument('--symbol', type=str, default='BTC', help='Trading symbol')
    parser.add_argument('--size', type=float, default=0.001, help='Test size')
    parser.add_argument('--offset', type=float, default=100.0, help='Price offset above market')
    parser.add_argument('--testnet', action='store_true', default=True, help='Use testnet')
    parser.add_argument('--mainnet', action='store_true', help='Use mainnet (be careful!)')
    
    args = parser.parse_args()
    
    use_testnet = not args.mainnet  # Default to testnet unless mainnet specified
    
    if not use_testnet:
        confirm = input("⚠️  WARNING: Using MAINNET! Type 'MAINNET' to confirm: ")
        if confirm != 'MAINNET':
            logger.error("Mainnet not confirmed. Exiting.")
            return
    
    await test_stop_limit_buy(
        symbol=args.symbol,
        test_size=args.size,
        price_offset=args.offset,
        use_testnet=use_testnet
    )


if __name__ == "__main__":
    asyncio.run(main())