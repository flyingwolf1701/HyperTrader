"""
Demonstration of Trading Capabilities
Shows both LONG and SHORT position management
"""
import sys
from pathlib import Path
from decimal import Decimal
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from exchange import HyperliquidExchangeClient


def demonstrate_trading():
    """Demonstrate trading capabilities without actually placing orders"""
    
    logger.info("=" * 60)
    logger.info("TRADING CAPABILITIES DEMONSTRATION")
    logger.info("=" * 60)
    
    try:
        # Initialize exchange client
        client = HyperliquidExchangeClient(testnet=True)
        
        # Get account info
        balance = client.get_balance("USDC")
        logger.info(f"\nAccount Balance: ${balance['free']:.2f} USDC available")
        
        # Get current ETH price
        symbol = "ETH/USDC:USDC"
        current_price = client.get_current_price(symbol)
        logger.info(f"Current ETH Price: ${current_price:.2f}")
        
        # Check current position
        position = client.get_position(symbol)
        if position:
            logger.info(f"\nCurrent Position:")
            logger.info(f"  - Type: {position['side'].upper()}")
            logger.info(f"  - Size: {position['contracts']} ETH")
            logger.info(f"  - Entry: ${position['entryPrice']:.2f}")
            logger.info(f"  - PnL: ${position['unrealizedPnl']:.2f}")
        else:
            logger.info("\nNo active position")
        
        # Demonstrate position sizing (user-defined)
        logger.info("\n" + "=" * 60)
        logger.info("POSITION SIZING (User-Defined)")
        logger.info("=" * 60)
        
        # Example position sizes
        position_sizes = [
            Decimal("100"),   # $100 position
            Decimal("500"),   # $500 position
            Decimal("1000"),  # $1000 position
        ]
        
        for size_usd in position_sizes:
            contracts = size_usd / current_price
            logger.info(f"${size_usd} position = {contracts:.6f} ETH")
            
            # With leverage
            for leverage in [5, 10, 20]:
                margin_required = size_usd / leverage
                logger.info(f"  - {leverage}x leverage: ${margin_required:.2f} margin required")
        
        # Demonstrate LONG capabilities
        logger.info("\n" + "=" * 60)
        logger.info("LONG POSITION CAPABILITIES")
        logger.info("=" * 60)
        logger.info("To open a LONG position (betting price will go UP):")
        logger.info("```python")
        logger.info('order = client.open_long(')
        logger.info('    symbol="ETH/USDC:USDC",')
        logger.info('    position_size_usd=Decimal("500"),  # $500 position')
        logger.info('    leverage=10  # Optional: set leverage')
        logger.info(')')
        logger.info("```")
        logger.info("This would:")
        logger.info(f"  - Buy {Decimal('500')/current_price:.6f} ETH")
        logger.info(f"  - At current price ${current_price:.2f}")
        logger.info(f"  - With 10x leverage (${Decimal('500')/10:.2f} margin)")
        
        # Demonstrate SHORT capabilities  
        logger.info("\n" + "=" * 60)
        logger.info("SHORT POSITION CAPABILITIES")
        logger.info("=" * 60)
        logger.info("To open a SHORT position (betting price will go DOWN):")
        logger.info("```python")
        logger.info('order = client.open_short(')
        logger.info('    symbol="ETH/USDC:USDC",')
        logger.info('    position_size_usd=Decimal("500"),  # $500 position')
        logger.info('    leverage=10  # Optional: set leverage')
        logger.info(')')
        logger.info("```")
        logger.info("This would:")
        logger.info(f"  - Sell {Decimal('500')/current_price:.6f} ETH")
        logger.info(f"  - At current price ${current_price:.2f}")
        logger.info(f"  - With 10x leverage (${Decimal('500')/10:.2f} margin)")
        
        # Demonstrate closing positions
        logger.info("\n" + "=" * 60)
        logger.info("CLOSING POSITIONS")
        logger.info("=" * 60)
        logger.info("To close any position (LONG or SHORT):")
        logger.info("```python")
        logger.info('order = client.close_position("ETH/USDC:USDC")')
        logger.info("```")
        logger.info("This automatically:")
        logger.info("  - Detects if position is LONG or SHORT")
        logger.info("  - Places opposite order to close")
        logger.info("  - Uses reduce_only=True for safety")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.success("✅ LONG positions supported (buy to open, sell to close)")
        logger.success("✅ SHORT positions supported (sell to open, buy to close)")
        logger.success("✅ User-defined position sizes in USD")
        logger.success("✅ Leverage support (1x to max allowed)")
        logger.success("✅ Automatic position detection and closing")
        logger.info("=" * 60)
        
        logger.warning("\nNOTE: This is a demonstration only - no orders were placed")
        logger.info("To actually trade, use the methods shown above")
        
    except Exception as e:
        logger.error(f"Error in demonstration: {e}")
        return False
    
    return True


if __name__ == "__main__":
    demonstrate_trading()