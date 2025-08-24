#!/usr/bin/env python3

import asyncio
import ccxt.async_support as ccxt
from app.core.config import settings
import logging
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_positions():
    """Debug position fetching with raw CCXT calls"""
    exchange = None
    try:
        # Create exchange directly
        exchange = ccxt.hyperliquid({
            'walletAddress': settings.HYPERLIQUID_WALLET_KEY,
            'privateKey': settings.HYPERLIQUID_PRIVATE_KEY,
            'options': {
                'testnet': True,
            },
            'sandbox': True
        })
        
        logger.info("Exchange created")
        
        # Load markets
        await exchange.load_markets()
        logger.info(f"Markets loaded: {len(exchange.markets)} total")
        
        # Method 1: fetch_positions with no params
        logger.info("\n" + "="*60)
        logger.info("Method 1: fetch_positions() with no params")
        try:
            positions1 = await exchange.fetch_positions()
            logger.info(f"Result: {json.dumps(positions1, indent=2, default=str)}")
        except Exception as e:
            logger.error(f"Failed: {e}")
        
        # Method 2: fetch_positions with user param
        logger.info("\n" + "="*60)
        logger.info("Method 2: fetch_positions() with user param")
        try:
            positions2 = await exchange.fetch_positions(params={'user': settings.HYPERLIQUID_WALLET_KEY})
            logger.info(f"Result: {json.dumps(positions2, indent=2, default=str)}")
        except Exception as e:
            logger.error(f"Failed: {e}")
        
        # Method 3: fetch_positions for specific symbol
        logger.info("\n" + "="*60)
        logger.info("Method 3: fetch_positions(['PURR/USDC:USDC'])")
        try:
            positions3 = await exchange.fetch_positions(['PURR/USDC:USDC'])
            logger.info(f"Result: {json.dumps(positions3, indent=2, default=str)}")
        except Exception as e:
            logger.error(f"Failed: {e}")
        
        # Method 4: Direct API call to get user state
        logger.info("\n" + "="*60)
        logger.info("Method 4: Direct API call - privatePostInfo")
        try:
            user_state = await exchange.privatePostInfo({
                'type': 'clearinghouseState',
                'user': settings.HYPERLIQUID_WALLET_KEY
            })
            logger.info(f"User state: {json.dumps(user_state, indent=2, default=str)}")
        except Exception as e:
            logger.error(f"Failed: {e}")
        
        # Method 5: Get account info
        logger.info("\n" + "="*60)
        logger.info("Method 5: fetch_balance()")
        try:
            balance = await exchange.fetch_balance()
            logger.info(f"Balance info: {json.dumps(balance['info'], indent=2, default=str)}")
        except Exception as e:
            logger.error(f"Failed: {e}")
            
        # Method 6: Get open orders
        logger.info("\n" + "="*60)
        logger.info("Method 6: fetch_open_orders()")
        try:
            orders = await exchange.fetch_open_orders()
            logger.info(f"Open orders: {len(orders)}")
            for order in orders:
                logger.info(f"  Order: {order['symbol']} {order['side']} {order['amount']} @ {order['price']}")
        except Exception as e:
            logger.error(f"Failed: {e}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        if exchange:
            await exchange.close()

if __name__ == "__main__":
    asyncio.run(debug_positions())