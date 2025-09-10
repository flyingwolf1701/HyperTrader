#!/usr/bin/env python3
"""
Test script for order fill detection via WebSocket
"""

import asyncio
import sys
import os
from decimal import Decimal
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from exchange.hyperliquid_sdk import HyperliquidClient
from core.websocket_client import HyperliquidWebSocketClient


async def handle_fill(order_id: str, is_buy: bool, price: Decimal, size: Decimal, timestamp: int):
    """Handle order fill notification"""
    logger.warning(
        f"ORDER FILLED! "
        f"{'BUY' if is_buy else 'SELL'} {size} @ ${price:.2f} "
        f"(Order ID: {order_id})"
    )


async def test_fill_detection():
    """Test order fill detection with real orders"""
    logger.info("Testing order fill detection...")
    
    try:
        # Initialize SDK client
        client = HyperliquidClient(use_testnet=True, use_sub_wallet=False)
        user_address = client.get_user_address()
        logger.info(f"User address: {user_address}")
        
        # Initialize WebSocket client
        ws_client = HyperliquidWebSocketClient(
            testnet=True,
            user_address=user_address
        )
        
        # Connect WebSocket
        if not await ws_client.connect():
            logger.error("Failed to connect WebSocket")
            return
        
        # Subscribe to user fills
        await ws_client.subscribe_to_user_fills(user_address)
        logger.info("Subscribed to user fills")
        
        # Note: We're only testing fill detection, not the full unit tracking
        
        # Start listening
        listen_task = asyncio.create_task(ws_client.listen())
        logger.info("WebSocket listening for fills...")
        
        # Wait a moment for everything to connect
        await asyncio.sleep(2)
        
        # Get current ETH price
        current_price = client.get_current_price("ETH")
        logger.info(f"Current ETH price: ${current_price:.2f}")
        
        # Place a test order that's likely to fill
        logger.info("\nPlacing a test order that might fill...")
        
        # Calculate a competitive price (at or near market)
        test_price = current_price  # At market price for higher chance of fill
        test_size = Decimal("0.003")  # Small size
        
        logger.info(f"Placing BUY order: {test_size} ETH @ ${test_price:.2f}")
        result = client.place_limit_order(
            symbol="ETH",
            is_buy=True,
            price=test_price,
            size=test_size,
            reduce_only=False,
            post_only=False  # Allow taker order for immediate fill
        )
        
        if result.success:
            logger.info(f"Order placed! Order ID: {result.order_id}")
            
            if result.filled_size and result.filled_size > 0:
                logger.info(f"Order already filled! Size: {result.filled_size}")
            else:
                logger.info("Waiting for fill notification via WebSocket...")
                
                # Wait for fill or timeout
                await asyncio.sleep(10)
                
                # Check order status
                orders = client.get_open_orders("ETH")
                if any(o['oid'] == result.order_id for o in orders):
                    logger.info("Order still open, cancelling...")
                    client.cancel_order("ETH", result.order_id)
                else:
                    logger.info("Order no longer open (likely filled)")
        else:
            logger.error(f"Failed to place order: {result.error_message}")
        
        # Keep listening for a bit more
        logger.info("\nContinuing to listen for any fills...")
        await asyncio.sleep(5)
        
        # Clean up
        await ws_client.disconnect()
        listen_task.cancel()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run test"""
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    logger.info("=" * 60)
    logger.info("ORDER FILL DETECTION TEST")
    logger.info("=" * 60)
    
    await test_fill_detection()
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())