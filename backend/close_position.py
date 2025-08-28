"""
Quick script to close all positions on Hyperliquid
"""
import sys
import asyncio
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.exchange.exchange_client import HyperliquidExchangeClient
from loguru import logger

async def close_all_positions():
    """Close all open positions"""
    try:
        # Initialize exchange client
        exchange = HyperliquidExchangeClient(testnet=True)
        
        # Get position for ETH
        symbol = "ETH/USDC:USDC"
        position = exchange.get_position(symbol)
        
        if position:
            side = position.get('side')
            contracts = abs(position.get('contracts', 0))
            
            if contracts > 0:
                logger.info(f"Found {side} position: {contracts} ETH")
                
                if side == 'long':
                    logger.info("Closing long position...")
                    result = await exchange.sell_long_eth(
                        symbol=symbol,
                        eth_amount=Decimal(str(contracts)),
                        reduce_only=True
                    )
                    if result:
                        logger.success(f"✅ Closed long position: {contracts} ETH")
                    else:
                        logger.error("Failed to close long position")
                        
                elif side == 'short':
                    logger.info("Closing short position...")
                    result = await exchange.close_short_eth(
                        symbol=symbol,
                        eth_amount=Decimal(str(contracts))
                    )
                    if result:
                        logger.success(f"✅ Closed short position: {contracts} ETH")
                    else:
                        logger.error("Failed to close short position")
            else:
                logger.info("No open positions found")
        else:
            logger.info("No positions to close")
            
        # Verify position is closed
        position = exchange.get_position(symbol)
        if position and abs(position.get('contracts', 0)) > 0:
            logger.warning("Position still exists after close attempt")
        else:
            logger.success("✅ All positions successfully closed")
            logger.info("You can now start a fresh strategy")
            
    except Exception as e:
        logger.error(f"Error closing positions: {e}")

if __name__ == "__main__":
    asyncio.run(close_all_positions())