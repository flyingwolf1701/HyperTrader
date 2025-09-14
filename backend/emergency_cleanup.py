#!/usr/bin/env python3
"""
Emergency script to clean up excess orders
Run this when you have way too many orders stuck on the exchange
"""

import asyncio
import sys
from decimal import Decimal
from loguru import logger
from src.exchange.hyperliquid_sdk import HyperliquidClient

async def emergency_cleanup(symbol: str, wallet_type: str, testnet: bool = False):
    """Emergency cleanup of excess orders"""
    
    # Initialize SDK
    use_sub_wallet = (wallet_type == "hedge")
    sdk = HyperliquidClient(use_testnet=testnet, use_sub_wallet=use_sub_wallet)
    
    logger.warning(f"🚨 EMERGENCY CLEANUP for {symbol}")
    
    # Get all open orders
    orders = sdk.get_open_orders(symbol)
    
    if not orders:
        logger.info("✅ No open orders found")
        return
    
    logger.error(f"🚨 Found {len(orders)} open orders!")
    
    # Cancel ALL orders
    cancelled = 0
    failed = 0
    
    for order in orders:
        order_id = order.get('oid')
        order_type = order.get('orderType')
        side = order.get('side')
        price = order.get('limitPx')
        
        logger.info(f"Cancelling {order_type} {side} order at ${price}: {order_id}")
        
        try:
            if sdk.cancel_order(symbol, order_id):
                cancelled += 1
                logger.info(f"✅ Cancelled {order_id}")
            else:
                failed += 1
                logger.error(f"❌ Failed to cancel {order_id}")
        except Exception as e:
            failed += 1
            logger.error(f"Error cancelling {order_id}: {e}")
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.1)
    
    logger.warning(f"🧹 CLEANUP COMPLETE: Cancelled {cancelled}/{len(orders)} orders")
    
    if failed > 0:
        logger.error(f"⚠️ {failed} orders failed to cancel - may need manual intervention")
    
    # Check remaining orders
    await asyncio.sleep(2)
    remaining = sdk.get_open_orders(symbol)
    if remaining:
        logger.error(f"⚠️ Still {len(remaining)} orders remaining after cleanup")
    else:
        logger.info("✅ All orders successfully cleared")

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Emergency order cleanup")
    parser.add_argument("--symbol", required=True, help="Trading symbol (e.g., SOL)")
    parser.add_argument("--wallet", choices=["long", "hedge"], required=True, help="Wallet type")
    parser.add_argument("--testnet", action="store_true", help="Use testnet")
    
    args = parser.parse_args()
    
    await emergency_cleanup(args.symbol, args.wallet, args.testnet)

if __name__ == "__main__":
    asyncio.run(main())