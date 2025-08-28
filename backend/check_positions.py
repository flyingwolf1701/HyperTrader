"""
Check actual positions on Hyperliquid exchange
"""
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.exchange.exchange_client import HyperliquidExchangeClient
from loguru import logger

def check_positions():
    """Check all positions on the exchange"""
    try:
        # Initialize exchange client
        exchange = HyperliquidExchangeClient(testnet=True)
        
        # Get balance
        usdc_balance = exchange.get_balance("USDC")
        logger.info(f"USDC Balance: Free=${usdc_balance['free']}, Used=${usdc_balance['used']}, Total=${usdc_balance['total']}")
        
        # Check ETH position
        symbol = "ETH/USDC:USDC"
        position = exchange.get_position(symbol)
        
        if position:
            logger.info(f"\nPosition found for {symbol}:")
            logger.info(f"  Side: {position.get('side')}")
            logger.info(f"  Contracts: {position.get('contracts')}")
            logger.info(f"  Entry Price: ${position.get('markPrice')}")
            logger.info(f"  Unrealized PnL: ${position.get('unrealizedPnl')}")
            logger.info(f"  Percentage: {position.get('percentage')}%")
            
            # This is the leftover from previous trading session
            if abs(position.get('contracts', 0)) < 0.025:  # Very small position
                logger.warning("\n⚠️ This is a tiny leftover position (dust)")
                logger.info("This is likely from the previous incomplete RETRACEMENT phase")
                logger.info("It's 0.0219 ETH = about $99 worth")
                logger.info("\nOptions:")
                logger.info("1. Manually close on Hyperliquid interface")
                logger.info("2. Run: uv run python close_position.py")
                logger.info("3. Or incorporate this remainder into new strategy")
        else:
            logger.success("✅ No open positions found")
            logger.info("Ready to start fresh strategy")
            
    except Exception as e:
        logger.error(f"Error checking positions: {e}")

if __name__ == "__main__":
    check_positions()