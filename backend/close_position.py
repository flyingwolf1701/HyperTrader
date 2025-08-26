"""
Close existing position script
"""
import sys
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.exchange.exchange_client import HyperliquidExchangeClient


def close_position():
    """Close existing ETH position"""
    logger.info("Closing existing ETH position...")
    
    try:
        # Initialize exchange client
        client = HyperliquidExchangeClient(testnet=True)
        
        # Check current position
        symbol = "ETH/USDC:USDC"
        position = client.get_position(symbol)
        
        if position:
            logger.info(f"Current position: {position['side']} {position['contracts']} ETH")
            
            # Close position
            order = client.close_position(symbol)
            
            if order:
                logger.success(f"Position closed successfully. Order ID: {order.get('id', 'N/A')}")
            else:
                logger.error("Failed to close position")
        else:
            logger.info("No position to close")
            
    except Exception as e:
        logger.error(f"Error closing position: {e}")


if __name__ == "__main__":
    close_position()
