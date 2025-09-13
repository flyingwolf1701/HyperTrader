#!/usr/bin/env python3
"""
Simple test to place a buy order at current_unit + 1
Mimics what should happen when a stop-loss triggers
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


async def place_buy_at_unit_plus_one(
    symbol: str = "BTC", 
    unit_size: float = 5.0,
    fragment_usd: float = 500.0,
    use_testnet: bool = True
):
    """
    Place a buy order at current_unit + 1
    
    Args:
        symbol: Trading symbol
        unit_size: USD per unit
        fragment_usd: USD value to buy
        use_testnet: Whether to use testnet
    """
    # Initialize
    load_dotenv()
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    logger.info(f"Testing buy order placement for {symbol}")
    logger.info(f"Unit size: ${unit_size}")
    logger.info(f"Fragment value: ${fragment_usd}")
    
    # Initialize SDK client
    client = HyperliquidClient(use_testnet=use_testnet)
    
    # Get current market price
    current_price = client.get_current_price(symbol)
    logger.info(f"Current market price: ${current_price:.2f}")
    
    # Calculate current unit (unit 0 = entry price)
    # For this test, assume we're at unit 0
    current_unit = 0
    entry_price = current_price  # Pretend we entered at current price
    
    # Calculate unit+1 price
    unit_plus_one_price = entry_price + Decimal(str(unit_size))
    logger.info(f"Current unit: {current_unit}")
    logger.info(f"Unit +1 price: ${unit_plus_one_price:.2f}")
    
    # Calculate size
    size = Decimal(str(fragment_usd)) / unit_plus_one_price
    logger.info(f"Order size: {size:.6f} {symbol}")
    
    # Determine order type based on price comparison
    logger.info("\n" + "="*50)
    
    if unit_plus_one_price > current_price:
        logger.warning(f"🎯 Unit+1 price ${unit_plus_one_price:.2f} > Market ${current_price:.2f}")
        logger.warning("Using STOP LIMIT BUY (should wait for price to rise)")
        
        # Use stop limit buy
        result = client.place_stop_limit_buy(
            symbol=symbol,
            size=size,
            trigger_price=unit_plus_one_price,
            limit_price=unit_plus_one_price,
            reduce_only=False
        )
        
        if result.success:
            logger.warning(f"✅ STOP LIMIT BUY PLACED!")
            logger.info(f"   Order ID: {result.order_id}")
            logger.info(f"   Trigger: ${unit_plus_one_price:.2f}")
            logger.info(f"   Size: {size:.6f} {symbol}")
            logger.info(f"   Value: ${fragment_usd}")
            logger.info("\n✨ This order should appear in your orders list")
            logger.info("   It will trigger when price rises to the trigger level")
        else:
            logger.error(f"❌ FAILED: {result.error_message}")
            
    else:
        logger.info(f"📉 Unit+1 price ${unit_plus_one_price:.2f} <= Market ${current_price:.2f}")
        logger.info("Would use regular limit buy")
        
        result = client.place_limit_order(
            symbol=symbol,
            is_buy=True,
            price=unit_plus_one_price,
            size=size,
            reduce_only=False,
            post_only=True
        )
        
        if result.success:
            logger.warning(f"✅ LIMIT BUY PLACED!")
            logger.info(f"   Order ID: {result.order_id}")
        else:
            logger.error(f"❌ FAILED: {result.error_message}")
    
    # Check open orders
    await asyncio.sleep(2)
    orders = client.get_open_orders(symbol)
    logger.info(f"\n📊 Open orders for {symbol}: {len(orders)}")
    
    # Show orders with TP/SL
    tp_sl_orders = [o for o in orders if hasattr(o, 'order_type') and 'tp' in str(o.order_type).lower()]
    if tp_sl_orders:
        logger.warning(f"   TP/SL orders found: {len(tp_sl_orders)}")
    
    logger.info("\n" + "="*50)
    logger.info("TEST COMPLETE - Check Hyperliquid interface")
    logger.info("="*50)


async def main():
    parser = argparse.ArgumentParser(description='Test buy order at current+1 unit')
    parser.add_argument('--symbol', type=str, default='BTC', help='Trading symbol')
    parser.add_argument('--unit-size', type=float, default=5.0, help='USD per unit')
    parser.add_argument('--fragment', type=float, default=500.0, help='Fragment value in USD')
    parser.add_argument('--testnet', action='store_true', default=True, help='Use testnet')
    parser.add_argument('--mainnet', action='store_true', help='Use mainnet')
    
    args = parser.parse_args()
    
    use_testnet = not args.mainnet
    
    if not use_testnet:
        confirm = input("⚠️  WARNING: Using MAINNET! Type 'MAINNET' to confirm: ")
        if confirm != 'MAINNET':
            logger.error("Mainnet not confirmed. Exiting.")
            return
    
    await place_buy_at_unit_plus_one(
        symbol=args.symbol,
        unit_size=args.unit_size,
        fragment_usd=args.fragment,
        use_testnet=use_testnet
    )


if __name__ == "__main__":
    asyncio.run(main())