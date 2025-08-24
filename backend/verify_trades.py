#!/usr/bin/env python3

import asyncio
from app.services.exchange import exchange_manager
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_trades():
    """Verify recent trades and orders"""
    try:
        # Initialize exchange
        await exchange_manager.initialize()
        logger.info("Exchange initialized")
        
        # Check recent trades
        logger.info(f"\n{'='*60}")
        logger.info("RECENT TRADES:")
        logger.info(f"{'='*60}")
        
        trades = await exchange_manager.fetch_my_trades("PURR/USDC:USDC", limit=10)
        for trade in trades:
            logger.info(f"\nTrade ID: {trade.id}")
            logger.info(f"  Symbol: {trade.symbol}")
            logger.info(f"  Side: {trade.side}")
            logger.info(f"  Amount: {trade.amount}")
            logger.info(f"  Price: ${trade.price}")
            logger.info(f"  Cost: ${trade.cost}")
            logger.info(f"  DateTime: {trade.datetime}")
        
        # Check open orders
        logger.info(f"\n{'='*60}")
        logger.info("OPEN ORDERS:")
        logger.info(f"{'='*60}")
        
        orders = await exchange_manager.fetch_open_orders("PURR/USDC:USDC")
        for order in orders:
            logger.info(f"\nOrder ID: {order.id}")
            logger.info(f"  Symbol: {order.symbol}")
            logger.info(f"  Type: {order.type}")
            logger.info(f"  Side: {order.side}")
            logger.info(f"  Amount: {order.amount}")
            logger.info(f"  Price: ${order.price}")
            logger.info(f"  Status: {order.status}")
            
        # Try to get positions with direct API call
        logger.info(f"\n{'='*60}")
        logger.info("DIRECT POSITION CHECK:")
        logger.info(f"{'='*60}")
        
        # Try without user param
        try:
            positions1 = await exchange_manager.exchange.fetch_positions()
            logger.info(f"Positions without user param: {positions1}")
        except Exception as e:
            logger.info(f"Without user param failed: {e}")
        
        # Try with user param  
        try:
            positions2 = await exchange_manager.exchange.fetch_positions(params={'user': settings.HYPERLIQUID_WALLET_KEY})
            logger.info(f"Positions with user param: {positions2}")
        except Exception as e:
            logger.info(f"With user param failed: {e}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await exchange_manager.close()

if __name__ == "__main__":
    asyncio.run(verify_trades())