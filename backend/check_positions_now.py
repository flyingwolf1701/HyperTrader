#!/usr/bin/env python3

import asyncio
from app.services.exchange import exchange_manager
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_positions():
    """Check current positions"""
    try:
        # Initialize exchange
        await exchange_manager.initialize()
        logger.info("Exchange initialized")
        
        # Get positions
        positions = await exchange_manager.fetch_positions()
        logger.info(f"\n{'='*60}")
        logger.info(f"CURRENT POSITIONS: {len(positions)}")
        logger.info(f"{'='*60}")
        
        for pos in positions:
            logger.info(f"\nSymbol: {pos.symbol}")
            logger.info(f"  Side: {pos.side}")
            logger.info(f"  Size: {pos.size}")
            logger.info(f"  Contracts: {pos.contracts}")
            logger.info(f"  Entry Price: ${pos.entry_price}")
            logger.info(f"  Mark Price: ${pos.mark_price}")
            logger.info(f"  Notional: ${pos.notional}")
            logger.info(f"  PnL: ${pos.pnl}")
            logger.info(f"  Percentage: {pos.percentage}%")
        
        # Now test SHORT on the perpetual
        logger.info(f"\n{'='*60}")
        logger.info("Now testing SHORT on PURR/USDC:USDC...")
        logger.info(f"{'='*60}")
        
        current_price = await exchange_manager.get_current_price("PURR/USDC:USDC")
        logger.info(f"Current price: ${current_price}")
        
        # Short 10 PURR
        logger.info("Placing SHORT order (sell) for 10 PURR...")
        result = await exchange_manager.place_order(
            symbol="PURR/USDC:USDC",
            order_type="market",
            side="sell",  # SELL = SHORT for perpetuals
            amount=10.0,
            price=current_price
        )
        
        if result.success:
            logger.info(f"✅ SHORT order successful!")
            logger.info(f"  Order ID: {result.order_id}")
        else:
            logger.error(f"❌ SHORT order failed: {result.error_message}")
            
        # Check positions again
        await asyncio.sleep(1)
        positions_after = await exchange_manager.fetch_positions()
        logger.info(f"\n{'='*60}")
        logger.info(f"POSITIONS AFTER SHORT: {len(positions_after)}")
        logger.info(f"{'='*60}")
        
        for pos in positions_after:
            logger.info(f"\nSymbol: {pos.symbol}")
            logger.info(f"  Side: {pos.side}")
            logger.info(f"  Size: {pos.size}")
            logger.info(f"  Contracts: {pos.contracts}")
            logger.info(f"  Entry Price: ${pos.entry_price}")
            logger.info(f"  PnL: ${pos.pnl}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await exchange_manager.close()

if __name__ == "__main__":
    asyncio.run(check_positions())