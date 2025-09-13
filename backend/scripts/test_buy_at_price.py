#!/usr/bin/env python3
"""
Test placing a buy order at a specific price
Direct test of stop limit buy functionality
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


async def place_buy_at_price(
    symbol: str,
    target_price: float,
    position_size_usd: float,
    use_testnet: bool = True
):
    """
    Place a buy order at a specific price
    
    Args:
        symbol: Trading symbol (e.g., "BTC")
        target_price: Exact price to place buy order at (e.g., 115400)
        position_size_usd: Position size in USD (e.g., 500)
        use_testnet: Whether to use testnet
    """
    # Initialize
    load_dotenv()
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    logger.info("="*60)
    logger.info(f"TESTING BUY ORDER AT SPECIFIC PRICE")
    logger.info("="*60)
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Target buy price: ${target_price:,.2f}")
    logger.info(f"Position size: ${position_size_usd:,.2f}")
    logger.info(f"Network: {'TESTNET' if use_testnet else 'MAINNET'}")
    
    # Initialize SDK client
    client = HyperliquidClient(use_testnet=use_testnet)
    
    # Get current market price
    current_price = client.get_current_price(symbol)
    logger.info(f"Current market price: ${current_price:,.2f}")
    
    # Calculate order size
    target_price_decimal = Decimal(str(target_price))
    size = Decimal(str(position_size_usd)) / target_price_decimal
    logger.info(f"Order size: {size:.6f} {symbol}")
    
    # Determine order type based on price comparison
    logger.info("\n" + "="*60)
    
    if target_price_decimal > current_price:
        # Price is above market - need stop limit buy
        price_diff = target_price_decimal - current_price
        logger.warning(f"🎯 TARGET PRICE IS ABOVE MARKET by ${price_diff:,.2f}")
        logger.warning(f"   Market: ${current_price:,.2f}")
        logger.warning(f"   Target: ${target_price:,.2f}")
        logger.info("\nUsing STOP LIMIT BUY order (waits for price to rise)")
        
        # Place stop limit buy
        result = client.place_stop_limit_buy(
            symbol=symbol,
            size=size,
            trigger_price=target_price_decimal,
            limit_price=target_price_decimal,  # Same as trigger for exact execution
            reduce_only=False
        )
        
        if result.success:
            logger.info("\n" + "="*60)
            logger.warning("✅ STOP LIMIT BUY ORDER PLACED SUCCESSFULLY!")
            logger.info("="*60)
            logger.info(f"Order ID: {result.order_id}")
            logger.info(f"Trigger Price: ${target_price:,.2f}")
            logger.info(f"Limit Price: ${target_price:,.2f}")
            logger.info(f"Size: {size:.6f} {symbol}")
            logger.info(f"Value: ${position_size_usd:,.2f}")
            logger.info("\n📌 This order will:")
            logger.info("   - Wait dormant until price rises to ${:,.2f}".format(target_price))
            logger.info("   - Then become active and try to fill at that price")
            logger.info("   - Should appear in Hyperliquid as a TP/SL order")
        else:
            logger.error("\n" + "="*60)
            logger.error("❌ STOP LIMIT BUY ORDER FAILED!")
            logger.error("="*60)
            logger.error(f"Error: {result.error_message}")
            logger.error("\nPossible reasons:")
            logger.error("1. API doesn't support 'tp' type for entries")
            logger.error("2. Insufficient balance")
            logger.error("3. Order size too small")
            logger.error("4. Price precision issues")
            
    else:
        # Price is at or below market - regular limit buy
        price_diff = current_price - target_price_decimal
        logger.info(f"📉 TARGET PRICE IS BELOW MARKET by ${price_diff:,.2f}")
        logger.info(f"   Market: ${current_price:,.2f}")
        logger.info(f"   Target: ${target_price:,.2f}")
        logger.info("\nUsing REGULAR LIMIT BUY order")
        
        result = client.place_limit_order(
            symbol=symbol,
            is_buy=True,
            price=target_price_decimal,
            size=size,
            reduce_only=False,
            post_only=True  # Maker only
        )
        
        if result.success:
            logger.info("\n" + "="*60)
            logger.warning("✅ LIMIT BUY ORDER PLACED SUCCESSFULLY!")
            logger.info("="*60)
            logger.info(f"Order ID: {result.order_id}")
            logger.info(f"Price: ${target_price:,.2f}")
            logger.info(f"Size: {size:.6f} {symbol}")
            logger.info(f"Value: ${position_size_usd:,.2f}")
        else:
            logger.error("\n" + "="*60)
            logger.error("❌ LIMIT BUY ORDER FAILED!")
            logger.error("="*60)
            logger.error(f"Error: {result.error_message}")
    
    # Check open orders
    logger.info("\n" + "="*60)
    logger.info("VERIFYING ORDER...")
    logger.info("="*60)
    
    await asyncio.sleep(2)
    orders = client.get_open_orders(symbol)
    logger.info(f"Total open orders for {symbol}: {len(orders)}")
    
    # Try to find our order
    if result.success and result.order_id:
        found = False
        for order in orders:
            if hasattr(order, 'order_id') and str(order.order_id) == str(result.order_id):
                found = True
                logger.warning(f"✅ Order verified in open orders list!")
                break
        
        if not found:
            logger.warning("⚠️  Order not found in open orders list")
            logger.info("   It may have already executed or there may be a delay")
    
    logger.info("\n" + "="*60)
    logger.info("TEST COMPLETE")
    logger.info("="*60)
    logger.info("Check your Hyperliquid interface to verify the order")
    if target_price_decimal > current_price:
        logger.info("Look for TP/SL indicator on the order")


async def main():
    parser = argparse.ArgumentParser(description='Test buy order at specific price')
    parser.add_argument('--symbol', type=str, default='BTC', required=False, help='Trading symbol (default: BTC)')
    parser.add_argument('--price', type=float, required=True, help='Target buy price (e.g., 115400)')
    parser.add_argument('--size', type=float, default=500.0, help='Position size in USD (default: 500)')
    parser.add_argument('--testnet', action='store_true', default=True, help='Use testnet (default)')
    parser.add_argument('--mainnet', action='store_true', help='Use mainnet (be careful!)')
    
    args = parser.parse_args()
    
    use_testnet = not args.mainnet
    
    if not use_testnet:
        confirm = input("⚠️  WARNING: Using MAINNET! Type 'MAINNET' to confirm: ")
        if confirm != 'MAINNET':
            logger.error("Mainnet not confirmed. Exiting.")
            return
    
    await place_buy_at_price(
        symbol=args.symbol,
        target_price=args.price,
        position_size_usd=args.size,
        use_testnet=use_testnet
    )


if __name__ == "__main__":
    asyncio.run(main())