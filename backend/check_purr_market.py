#!/usr/bin/env python3

import asyncio
from app.services.exchange import exchange_manager
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_purr_market():
    """Check PURR market details"""
    try:
        # Initialize exchange
        await exchange_manager.initialize()
        logger.info("Exchange initialized")
        
        # Check PURR/USDC market details
        symbols_to_check = ["PURR/USDC", "PURR/USDC:USDC", "PURR-PERP"]
        
        for symbol in symbols_to_check:
            if symbol in exchange_manager.exchange.markets:
                market = exchange_manager.exchange.markets[symbol]
                logger.info(f"\n{'='*60}")
                logger.info(f"Market: {symbol}")
                logger.info(f"  Type: {market.get('type')}")
                logger.info(f"  Spot: {market.get('spot')}")
                logger.info(f"  Swap: {market.get('swap')}")
                logger.info(f"  Future: {market.get('future')}")
                logger.info(f"  Option: {market.get('option')}")
                logger.info(f"  Contract: {market.get('contract')}")
                logger.info(f"  Settle: {market.get('settle')}")
                logger.info(f"  Base: {market.get('base')}")
                logger.info(f"  Quote: {market.get('quote')}")
                logger.info(f"  Active: {market.get('active')}")
                logger.info(f"  Margin: {market.get('margin')}")
                logger.info(f"  Limits: {market.get('limits')}")
        
        # Try to place a PERPETUAL/FUTURES order on PURR
        logger.info(f"\n{'='*60}")
        logger.info("Trying PURR/USDC:USDC (perpetual format)...")
        
        # Get current price
        price = await exchange_manager.get_current_price("PURR/USDC:USDC")
        if price:
            logger.info(f"Current PURR/USDC:USDC price: ${price}")
            
            # Calculate small position size (around $25 worth)
            position_value_usd = 25.0
            amount = position_value_usd / float(price)
            
            logger.info(f"Attempting to buy {amount:.2f} PURR (${position_value_usd} worth)...")
            
            result = await exchange_manager.place_order(
                symbol="PURR/USDC:USDC",
                order_type="market",
                side="buy",
                amount=amount,
                price=price
            )
            
            if result.success:
                logger.info(f"✅ Order successful!")
                logger.info(f"  Order ID: {result.order_id}")
                logger.info(f"  Average Price: {result.average_price}")
                logger.info(f"  Cost: {result.cost}")
            else:
                logger.error(f"❌ Order failed: {result.error_message}")
        else:
            logger.error("Could not get price for PURR/USDC:USDC")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await exchange_manager.close()

if __name__ == "__main__":
    asyncio.run(check_purr_market())