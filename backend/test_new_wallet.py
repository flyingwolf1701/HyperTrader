#!/usr/bin/env python3

import asyncio
from app.services.exchange import exchange_manager
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_new_wallet():
    """Test the new wallet configuration"""
    try:
        logger.info("=" * 60)
        logger.info("TESTING NEW WALLET CONFIGURATION")
        logger.info("=" * 60)
        
        # Show new configuration
        logger.info(f"New Wallet Address: {settings.HYPERLIQUID_WALLET_KEY}")
        
        # Initialize exchange
        await exchange_manager.initialize()
        logger.info("Exchange initialized successfully")
        
        # Check balances
        balances = await exchange_manager.fetch_all_balances()
        logger.info(f"\nAccount Balances:")
        for currency, balance in balances.items():
            if balance > 0:
                logger.info(f"  {currency}: {balance}")
        
        # Check positions
        positions = await exchange_manager.fetch_positions()
        logger.info(f"\nCurrent Positions: {len(positions)}")
        for pos in positions:
            logger.info(f"  {pos.symbol}: {pos.side} {pos.size} @ ${pos.entry_price} (PnL: ${pos.pnl})")
        
        # If we have an existing PURR position, let's close it
        purr_position = next((p for p in positions if p.symbol == "PURR/USDC:USDC"), None)
        
        if purr_position:
            logger.info(f"\n{'='*60}")
            logger.info(f"Found PURR position: {purr_position.side} {purr_position.size}")
            
            # Get current price
            current_price = await exchange_manager.get_current_price("PURR/USDC:USDC")
            logger.info(f"Current PURR price: ${current_price}")
            
            # Close the position by taking opposite side
            if purr_position.side == "short" or purr_position.contracts < 0:
                logger.info("Closing SHORT position by buying...")
                side = "buy"
            else:
                logger.info("Closing LONG position by selling...")
                side = "sell"
            
            amount = abs(float(purr_position.size)) if purr_position.size else abs(float(purr_position.contracts))
            
            result = await exchange_manager.place_order(
                symbol="PURR/USDC:USDC",
                order_type="market",
                side=side,
                amount=amount,
                price=current_price
            )
            
            if result.success:
                logger.info(f"✅ Position closed successfully!")
                logger.info(f"  Order ID: {result.order_id}")
            else:
                logger.error(f"❌ Failed to close position: {result.error_message}")
        else:
            logger.info("\nNo PURR position found to close")
            
        # Check final positions
        await asyncio.sleep(1)
        final_positions = await exchange_manager.fetch_positions()
        logger.info(f"\nFinal Positions: {len(final_positions)}")
        for pos in final_positions:
            logger.info(f"  {pos.symbol}: {pos.side} {pos.size} @ ${pos.entry_price}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await exchange_manager.close()

if __name__ == "__main__":
    asyncio.run(test_new_wallet())