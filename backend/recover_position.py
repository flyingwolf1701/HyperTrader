"""
Recovery script to attach HyperTrader to an existing position
"""
import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.strategy.strategy_manager import StrategyManager
from src.exchange.exchange_client import HyperliquidExchangeClient


async def recover_and_monitor():
    """Recover existing position and start monitoring"""
    
    logger.info("=" * 60)
    logger.info("HYPERTRADER POSITION RECOVERY")
    logger.info("=" * 60)
    
    # Initialize exchange client
    client = HyperliquidExchangeClient(testnet=True)
    symbol = "ETH/USDC:USDC"
    
    # Check for existing position
    position = client.get_position(symbol)
    
    if position:
        logger.success("Found existing position!")
        logger.info(f"  Side: {position['side']}")
        logger.info(f"  Size: {position['contracts']} ETH")
        logger.info(f"  Entry Price: ${position['entryPrice']}")
        logger.info(f"  Current PnL: ${position['unrealizedPnl']}")
        
        # Get current price
        current_price = client.get_current_price(symbol)
        logger.info(f"  Current Price: ${current_price}")
        
        # Initialize strategy manager
        manager = StrategyManager(testnet=True)
        
        # Create strategy state manually
        position_value = Decimal(str(position['contracts'])) * current_price
        
        success = await manager.start_strategy(
            symbol=symbol,
            position_size_usd=position_value,
            unit_size=Decimal("2.0"),
            leverage=10
        )
        
        if success:
            logger.success("Strategy attached to existing position!")
            logger.info("Monitoring price changes...")
            
            # Start monitoring
            await manager.ws_client.listen()
        else:
            logger.error("Failed to attach strategy")
            
    else:
        logger.warning("No existing position found")
        logger.info("Starting fresh strategy...")
        
        # Start new strategy
        manager = StrategyManager(testnet=True)
        success = await manager.start_strategy(
            symbol=symbol,
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("2.0"),
            leverage=10
        )
        
        if success:
            logger.success("New strategy started!")
            await manager.ws_client.listen()


if __name__ == "__main__":
    try:
        asyncio.run(recover_and_monitor())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")