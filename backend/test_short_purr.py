#!/usr/bin/env python3

import asyncio
from app.services.exchange import exchange_manager
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_short_purr():
    """Test placing a short position on PURR"""
    try:
        # Initialize exchange
        await exchange_manager.initialize()
        logger.info("Exchange initialized successfully")
        
        # Check if PURR market is available
        if not exchange_manager.is_market_available("PURR/USDC"):
            logger.error("PURR/USDC market not available")
            return
            
        logger.info("PURR/USDC market is available")
        
        # Get current price
        current_price = await exchange_manager.get_current_price("PURR/USDC")
        if current_price is None:
            logger.error("Could not get PURR price")
            return
            
        logger.info(f"Current PURR price: ${current_price}")
        
        # Check current positions
        positions = await exchange_manager.fetch_positions()
        logger.info(f"Current positions: {len(positions)}")
        for pos in positions:
            logger.info(f"  {pos.symbol}: {pos.side} {pos.size} @ ${pos.entry_price}")
        
        # Check balances
        balances = await exchange_manager.fetch_all_balances()
        logger.info(f"USDC Balance: {balances.get('USDC', 0)}")
        
        # Try to place a small short order
        logger.info("Attempting to place short order for 5 PURR...")
        
        result = await exchange_manager.place_order(
            symbol="PURR/USDC",
            order_type="market",
            side="sell",
            amount=5.0,  # 5 PURR
            price=current_price
        )
        
        if result.success:
            logger.info(f"✅ Short order placed successfully!")
            logger.info(f"Order ID: {result.order_id}")
            logger.info(f"Average Price: {result.average_price}")
            logger.info(f"Cost: {result.cost}")
        else:
            logger.error(f"❌ Order failed: {result.error_message}")
            
        # Check positions after trade
        positions_after = await exchange_manager.fetch_positions()
        logger.info(f"Positions after trade: {len(positions_after)}")
        for pos in positions_after:
            logger.info(f"  {pos.symbol}: {pos.side} {pos.size} @ ${pos.entry_price} (PnL: ${pos.pnl})")
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
    finally:
        await exchange_manager.close()

if __name__ == "__main__":
    asyncio.run(test_short_purr())