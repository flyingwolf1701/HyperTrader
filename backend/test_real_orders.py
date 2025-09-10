#!/usr/bin/env python3
"""
Test script for HyperTrader with real orders on testnet
Uses minimal position sizes for safety
"""

import asyncio
import sys
import os
from decimal import Decimal
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from exchange.hyperliquid_sdk import HyperliquidClient


async def test_sdk_connection():
    """Test basic SDK connection and market data"""
    logger.info("Testing SDK connection...")
    
    try:
        # Initialize client
        client = HyperliquidClient(use_testnet=True, use_sub_wallet=False)
        
        # Test 1: Get balance
        logger.info("\n1. Testing balance retrieval...")
        balance = client.get_balance()
        logger.info(f"   Balance: ${balance.total_value:.2f}")
        logger.info(f"   Available: ${balance.available:.2f}")
        
        # Test 2: Get current price
        logger.info("\n2. Testing price retrieval...")
        eth_price = client.get_current_price("ETH")
        logger.info(f"   ETH Price: ${eth_price:.2f}")
        
        # Test 3: Get positions
        logger.info("\n3. Testing position retrieval...")
        positions = client.get_positions()
        if positions:
            for symbol, pos in positions.items():
                logger.info(f"   {symbol}: {pos.size} @ ${pos.entry_price:.2f}")
        else:
            logger.info("   No open positions")
        
        # Test 4: Get open orders
        logger.info("\n4. Testing open orders retrieval...")
        orders = client.get_open_orders("ETH")
        logger.info(f"   Open orders: {len(orders)}")
        
        return True
        
    except Exception as e:
        logger.error(f"SDK test failed: {e}")
        return False


async def test_limit_orders():
    """Test placing and cancelling limit orders"""
    logger.info("\n\nTesting limit order placement...")
    
    try:
        client = HyperliquidClient(use_testnet=True, use_sub_wallet=False)
        
        # Get current price
        current_price = client.get_current_price("ETH")
        logger.info(f"Current ETH price: ${current_price:.2f}")
        
        # Calculate test order price (far from market to avoid execution)
        test_buy_price = current_price * Decimal("0.8")  # 20% below market
        test_sell_price = current_price * Decimal("1.2")  # 20% above market
        
        # Calculate minimum size for $10 order value
        min_value = Decimal("10.0")
        test_size = (min_value / test_buy_price) * Decimal("1.1")  # 10% above minimum
        test_size = test_size.quantize(Decimal("0.0001"))  # Round to 4 decimals
        
        # Test placing a buy limit order
        logger.info(f"\nPlacing test BUY order: {test_size} ETH @ ${test_buy_price:.2f}")
        buy_result = client.place_limit_order(
            symbol="ETH",
            is_buy=True,
            price=test_buy_price,
            size=test_size,
            reduce_only=False,
            post_only=True
        )
        
        if buy_result.success:
            logger.info(f"✓ Buy order placed successfully! Order ID: {buy_result.order_id}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Cancel the order
            logger.info(f"Cancelling order {buy_result.order_id}...")
            cancelled = client.cancel_order("ETH", buy_result.order_id)
            if cancelled:
                logger.info("✓ Order cancelled successfully!")
            else:
                logger.error("✗ Failed to cancel order")
        else:
            logger.error(f"✗ Failed to place buy order: {buy_result.error_message}")
        
        return True
        
    except Exception as e:
        logger.error(f"Limit order test failed: {e}")
        return False


async def main():
    """Run all tests"""
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    logger.info("=" * 60)
    logger.info("HYPERTRADER SDK TEST - TESTNET")
    logger.info("=" * 60)
    
    # Test SDK connection
    if not await test_sdk_connection():
        logger.error("SDK connection test failed. Exiting.")
        return
    
    # Ask user if they want to test order placement
    print("\nDo you want to test limit order placement? (y/n): ", end="")
    response = input().strip().lower()
    
    if response == 'y':
        await test_limit_orders()
    else:
        logger.info("Skipping order placement test")
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())