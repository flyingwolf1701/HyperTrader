#!/usr/bin/env python3

import asyncio
from app.services.exchange import exchange_manager
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def close_purr_short():
    """Close the short position on PURR by buying back"""
    try:
        # Initialize exchange
        await exchange_manager.initialize()
        logger.info("Exchange initialized")
        
        # Get current price
        current_price = await exchange_manager.get_current_price("PURR/USDC:USDC")
        logger.info(f"Current PURR price: ${current_price}")
        
        # Check current positions first
        positions = await exchange_manager.fetch_positions()
        logger.info(f"Current positions: {len(positions)}")
        for pos in positions:
            logger.info(f"  {pos.symbol}: {pos.side} {pos.size} contracts @ ${pos.entry_price}")
        
        # Close the short by buying back
        # Since we sold 10 PURR earlier (and maybe had a partial long before)
        # Let's buy back enough to close any short position
        logger.info("\nClosing SHORT position by buying PURR...")
        
        # Buy 10 PURR to close the short (or adjust based on your actual position)
        amount_to_buy = 10.0
        
        result = await exchange_manager.place_order(
            symbol="PURR/USDC:USDC",
            order_type="market",
            side="buy",  # BUY to close short
            amount=amount_to_buy,
            price=current_price
        )
        
        if result.success:
            logger.info(f"✅ Successfully closed short position!")
            logger.info(f"  Order ID: {result.order_id}")
            logger.info(f"  Bought {amount_to_buy} PURR at ~${current_price}")
        else:
            logger.error(f"❌ Failed to close short: {result.error_message}")
        
        # Check positions after closing
        await asyncio.sleep(1)
        positions_after = await exchange_manager.fetch_positions()
        logger.info(f"\nPositions after closing: {len(positions_after)}")
        for pos in positions_after:
            logger.info(f"  {pos.symbol}: {pos.side} {pos.size} @ ${pos.entry_price}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await exchange_manager.close()

if __name__ == "__main__":
    asyncio.run(close_purr_short())