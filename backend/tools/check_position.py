"""
Check and optionally close existing positions
"""
import sys
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.exchange.exchange_client import HyperliquidExchangeClient


def main():
    """Check existing positions"""
    
    logger.info("=" * 60)
    logger.info("CHECKING HYPERLIQUID POSITIONS")
    logger.info("=" * 60)
    
    client = HyperliquidExchangeClient(testnet=True)
    
    # Check balance
    balance = client.get_balance("USDC")
    logger.info(f"\nAccount Balance: ${balance['free']:.2f} USDC available")
    
    # Check ETH position
    symbol = "ETH/USDC:USDC"
    position = client.get_position(symbol)
    
    if position:
        logger.info(f"\nFound {symbol} Position:")
        logger.info(f"  Side: {position['side']}")
        logger.info(f"  Size: {position['contracts']} ETH")
        logger.info(f"  Entry Price: ${position['entryPrice']}")
        logger.info(f"  Mark Price: ${position.get('markPrice', 'N/A')}")
        logger.info(f"  Unrealized PnL: ${position['unrealizedPnl']}")
        logger.info(f"  Percentage: {position['percentage']:.2f}%")
        
        # Ask if user wants to close it
        response = input("\nDo you want to close this position? (y/n): ")
        
        if response.lower() == 'y':
            logger.info("Closing position...")
            order = client.close_position(symbol)
            if order:
                logger.success(f"Position closed! Order ID: {order.get('id', 'N/A')}")
            else:
                logger.error("Failed to close position")
        else:
            logger.info("Position left open")
    else:
        logger.info(f"\nNo position found for {symbol}")
    
    # Check all positions
    logger.info("\nChecking all positions...")
    try:
        all_positions = client.exchange.fetch_positions()
        if all_positions:
            logger.info(f"Found {len(all_positions)} total positions:")
            for pos in all_positions:
                if pos['contracts'] != 0:
                    logger.info(f"  - {pos['symbol']}: {pos['side']} {pos['contracts']}")
        else:
            logger.info("No active positions")
    except Exception as e:
        logger.error(f"Error fetching all positions: {e}")


if __name__ == "__main__":
    main()