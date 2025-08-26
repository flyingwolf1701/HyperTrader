"""
HyperTrader - Advanced Hedging Strategy v6.0.0
Main entry point for running the automated trading strategy
"""
import asyncio
import sys
import signal
from pathlib import Path
from decimal import Decimal
from typing import Optional
from loguru import logger
import argparse
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.strategy.strategy_manager import StrategyManager
from src.utils.config import settings


class HyperTrader:
    """Main application class for HyperTrader"""
    
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.strategy_manager = StrategyManager(testnet=testnet)
        self.is_running = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
    async def start(
        self,
        symbol: str,
        position_size_usd: Decimal,
        unit_size: Decimal,
        leverage: int = 10
    ):
        """Start the trading strategy"""
        try:
            logger.info("=" * 60)
            logger.info("HYPERTRADER - ADVANCED HEDGING STRATEGY v6.0.0")
            logger.info("=" * 60)
            logger.info(f"Network: {'TESTNET' if self.testnet else 'MAINNET'}")
            logger.info(f"Symbol: {symbol}")
            logger.info(f"Position Size: ${position_size_usd}")
            logger.info(f"Unit Size: ${unit_size}")
            logger.info(f"Leverage: {leverage}x")
            logger.info(f"Started at: {datetime.now().isoformat()}")
            logger.info("=" * 60)
            
            # Start the strategy
            success = await self.strategy_manager.start_strategy(
                symbol=symbol,
                position_size_usd=position_size_usd,
                unit_size=unit_size,
                leverage=leverage
            )
            
            if not success:
                logger.error("Failed to start strategy")
                return False
            
            self.is_running = True
            
            # Start monitoring in background
            self.monitoring_task = asyncio.create_task(self.monitor_strategy(symbol))
            
            # Start WebSocket listener
            logger.info("\nStarting real-time price monitoring...")
            await self.strategy_manager.ws_client.listen()
            
        except KeyboardInterrupt:
            logger.info("\nShutdown requested by user")
            await self.shutdown(symbol)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await self.shutdown(symbol)
    
    async def monitor_strategy(self, symbol: str):
        """Monitor strategy status and log updates"""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Get strategy status
                status = await self.strategy_manager.get_strategy_status(symbol)
                
                # Log summary
                logger.info("\n" + "-" * 40)
                logger.info("STRATEGY STATUS UPDATE")
                logger.info("-" * 40)
                logger.info(f"Phase: {status['phase']}")
                logger.info(f"Current Price: ${status['current_price']:.2f}")
                logger.info(f"Current Unit: {status['current_unit']}")
                logger.info(f"Peak: {status['peak_unit']} | Valley: {status['valley_unit']}")
                
                if status['position']['has_position']:
                    logger.info(f"Position: {status['position']['side']} | PnL: ${status['position']['pnl']:.2f}")
                
                logger.info(f"Position Value: ${status['position_allocation']:.2f}")
                logger.info(f"Resets Completed: {status['reset_count']}")
                
                # Calculate total return
                if status['initial_allocation'] > 0:
                    total_return = ((status['position_allocation'] - status['initial_allocation']) / status['initial_allocation']) * 100
                    logger.info(f"Total Return: {total_return:.2f}%")
                
                logger.info("-" * 40)
                
            except Exception as e:
                logger.error(f"Error in monitoring: {e}")
                await asyncio.sleep(5)
    
    async def shutdown(self, symbol: str):
        """Gracefully shutdown the strategy"""
        logger.info("\n" + "=" * 60)
        logger.info("SHUTTING DOWN HYPERTRADER")
        logger.info("=" * 60)
        
        self.is_running = False
        
        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        # Get final status
        try:
            status = await self.strategy_manager.get_strategy_status(symbol)
            logger.info(f"Final Phase: {status['phase']}")
            logger.info(f"Final Position Value: ${status['position_allocation']:.2f}")
            logger.info(f"Total Resets: {status['reset_count']}")
        except:
            pass
        
        # Ask about position closure
        if self.strategy_manager.strategies.get(symbol):
            logger.warning("\nWARNING: Active position detected")
            response = input("Close position before shutdown? (y/n): ")
            
            if response.lower() == 'y':
                await self.strategy_manager.stop_strategy(symbol, close_position=True)
                logger.info("Position closed")
            else:
                logger.warning("Position left open - monitor manually!")
        
        # Disconnect WebSocket
        if self.strategy_manager.ws_client.is_connected:
            await self.strategy_manager.ws_client.disconnect()
        
        logger.info("Shutdown complete")
        logger.info("=" * 60)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="HyperTrader - Advanced Hedging Strategy")
    
    # Required arguments
    parser.add_argument("symbol", help="Trading symbol (e.g., ETH/USDC:USDC)")
    parser.add_argument("position_size", type=float, help="Position size in USD")
    parser.add_argument("unit_size", type=float, help="Unit size in USD")
    
    # Optional arguments
    parser.add_argument("--leverage", type=int, default=10, help="Leverage (default: 10)")
    parser.add_argument("--mainnet", action="store_true", help="Use mainnet (default: testnet)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without placing orders")
    
    args = parser.parse_args()
    
    # Validate inputs
    if args.position_size <= 0:
        logger.error("Position size must be positive")
        return
    
    if args.unit_size <= 0:
        logger.error("Unit size must be positive")
        return
    
    if args.leverage < 1 or args.leverage > 100:
        logger.error("Leverage must be between 1 and 100")
        return
    
    # Safety check for mainnet
    if args.mainnet:
        logger.warning("=" * 60)
        logger.warning("WARNING: MAINNET MODE")
        logger.warning("This will trade with REAL funds!")
        logger.warning("=" * 60)
        response = input("Are you absolutely sure? Type 'YES' to continue: ")
        
        if response != "YES":
            logger.info("Mainnet trading cancelled")
            return
    
    # Create and start trader
    trader = HyperTrader(testnet=not args.mainnet)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("\nReceived interrupt signal")
        asyncio.create_task(trader.shutdown(args.symbol))
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start trading
    await trader.start(
        symbol=args.symbol,
        position_size_usd=Decimal(str(args.position_size)),
        unit_size=Decimal(str(args.unit_size)),
        leverage=args.leverage
    )


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )
    
    # Add file logging
    logger.add(
        "logs/hypertrader_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )
    
    # Run the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)