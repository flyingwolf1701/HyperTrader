"""
Close existing position on Hyperliquid
"""
import sys
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.exchange.exchange_client import HyperliquidExchangeClient


def main():
    """Close existing position"""
    
    logger.info("=" * 60)
    logger.info("CLOSING HYPERLIQUID POSITION")
    logger.info("=" * 60)
    
    client = HyperliquidExchangeClient(testnet=True)
    symbol = "ETH/USDC:USDC"
    
    # Check position
    position = client.get_position(symbol)
    
    if position:
        logger.info(f"Found {symbol} Position:")
        logger.info(f"  Side: {position['side']}")
        logger.info(f"  Size: {position['contracts']} ETH")
        logger.info(f"  Unrealized PnL: ${position['unrealizedPnl']}")
        
        # Close it
        logger.info("\nClosing position...")
        order = client.close_position(symbol)
        
        if order:
            logger.success(f"Position closed successfully!")
            logger.info(f"Order ID: {order.get('id', 'N/A')}")
        else:
            logger.error("Failed to close position")
    else:
        logger.info("No position found to close")
    
    # Check balance after
    balance = client.get_balance("USDC")
    logger.info(f"\nFinal Balance: ${balance['free']:.2f} USDC")


if __name__ == "__main__":
    main()