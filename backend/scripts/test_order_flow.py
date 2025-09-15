"""
Test script to verify the refactored order flow with direct REST response handling
"""

import asyncio
import sys
import os
from decimal import Decimal
from loguru import logger

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from exchange.hyperliquid_sdk import HyperliquidClient

async def test_order_flow():
    """Test the order placement and fill handling"""
    
    # Initialize SDK client
    client = HyperliquidClient(use_testnet=True, use_sub_wallet=False)
    
    symbol = "ETH"
    
    # Get current price
    current_price = client.get_current_price(symbol)
    logger.info(f"Current {symbol} price: ${current_price:.2f}")
    
    # Test 1: Place a limit buy order below market (should rest)
    logger.info("\n=== TEST 1: Limit Buy Below Market ===")
    buy_price = current_price * Decimal("0.99")  # 1% below market
    buy_size = Decimal("10") / buy_price  # $10 worth
    
    result = client.place_limit_order(
        symbol=symbol,
        is_buy=True,
        price=buy_price,
        size=buy_size,
        reduce_only=False,
        post_only=True
    )
    
    logger.info(f"Order Result: success={result.success}")
    if result.success:
        logger.info(f"  Order ID: {result.order_id}")
        logger.info(f"  Filled Size: {result.filled_size}")
        logger.info(f"  Average Price: {result.average_price}")
        
        # Cancel the order
        if result.filled_size == 0:
            logger.info("  Order is resting, cancelling...")
            cancelled = client.cancel_order(symbol, result.order_id)
            logger.info(f"  Cancelled: {cancelled}")
    else:
        logger.error(f"  Error: {result.error_message}")
    
    # Test 2: Place a stop loss order
    logger.info("\n=== TEST 2: Stop Loss Order ===")
    stop_price = current_price * Decimal("0.98")  # 2% below market
    stop_size = Decimal("0.001")  # Small test size
    
    result = client.place_stop_order(
        symbol=symbol,
        is_buy=False,
        size=stop_size,
        trigger_price=stop_price,
        reduce_only=False  # Set to False for testing without position
    )
    
    logger.info(f"Order Result: success={result.success}")
    if result.success:
        logger.info(f"  Order ID: {result.order_id}")
        logger.info(f"  Filled Size: {result.filled_size}")
        logger.info(f"  Trigger Price: {result.average_price}")
        
        # Cancel the order
        if result.filled_size == 0:
            logger.info("  Order is resting, cancelling...")
            cancelled = client.cancel_order(symbol, result.order_id)
            logger.info(f"  Cancelled: {cancelled}")
    else:
        logger.error(f"  Error: {result.error_message}")
    
    # Test 3: Place a stop limit buy above market
    logger.info("\n=== TEST 3: Stop Limit Buy Above Market ===")
    trigger_price = current_price * Decimal("1.01")  # 1% above market
    limit_price = trigger_price  # Same as trigger
    buy_size = Decimal("10") / trigger_price  # $10 worth
    
    result = client.place_stop_limit_buy(
        symbol=symbol,
        size=buy_size,
        trigger_price=trigger_price,
        limit_price=limit_price,
        reduce_only=False
    )
    
    logger.info(f"Order Result: success={result.success}")
    if result.success:
        logger.info(f"  Order ID: {result.order_id}")
        logger.info(f"  Filled Size: {result.filled_size}")
        logger.info(f"  Limit Price: {result.average_price}")
        
        # Cancel the order
        if result.filled_size == 0:
            logger.info("  Order is resting, cancelling...")
            cancelled = client.cancel_order(symbol, result.order_id)
            logger.info(f"  Cancelled: {cancelled}")
    else:
        logger.error(f"  Error: {result.error_message}")
    
    # Test 4: Get open orders to verify all were cancelled
    logger.info("\n=== TEST 4: Verify No Open Orders ===")
    open_orders = client.get_open_orders(symbol)
    logger.info(f"Open orders for {symbol}: {len(open_orders)}")
    for order in open_orders:
        logger.info(f"  Order: {order.get('oid')} - {order.get('side')} {order.get('sz')} @ {order.get('limitPx')}")
    
    logger.info("\n=== Order Flow Tests Complete ===")

if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Run the test
    asyncio.run(test_order_flow())