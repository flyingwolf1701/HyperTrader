"""
HyperTrader - Unified Entry Point
Combines all functionality with subcommands
"""
import asyncio
import sys
import signal
import subprocess
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Optional
from loguru import logger
import argparse

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core import HyperliquidWebSocketClient
from src.exchange import HyperliquidExchangeClient
from src.strategy.strategy_manager import StrategyManager
from src.utils import settings


class HyperTrader:
    """Main application class for HyperTrader"""
    
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.strategy_manager = StrategyManager(testnet=testnet)
        self.is_running = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
    async def start_trading(
        self,
        symbol: str,
        position_size_usd: Decimal,
        unit_size: Decimal,
        leverage: int = 10
    ):
        """Start the full trading strategy"""
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
        """Monitor strategy status - IMPROVED VERSION"""
        last_status = {}
        
        while self.is_running:
            try:
                await asyncio.sleep(30)
                
                status = await self.strategy_manager.get_strategy_status(symbol)
                
                # Only log if something meaningful changed
                status_changed = (
                    status.get('current_unit') != last_status.get('current_unit') or
                    status.get('phase') != last_status.get('phase') or
                    abs(status.get('position', {}).get('pnl', 0) - last_status.get('pnl', 0)) > 5  # >$5 PnL change
                )
                
                if status_changed or not last_status:
                    logger.info("\n" + "="*50)
                    logger.info("📊 STRATEGY UPDATE")
                    logger.info("="*50)
                    
                    # Check WebSocket connection health
                    ws_status = "🟢 Connected" if self.strategy_manager.ws_client.is_connected else "🔴 DISCONNECTED"
                    logger.info(f"WebSocket: {ws_status}")
                    
                    # Check for stale connection (no messages in 3+ minutes)
                    if hasattr(self.strategy_manager.ws_client, '_last_message_time'):
                        time_since_msg = (datetime.now() - self.strategy_manager.ws_client._last_message_time).total_seconds()
                        if time_since_msg > 180:  # 3 minutes
                            logger.warning(f"⚠️ No WebSocket messages for {time_since_msg:.0f}s")
                    
                    logger.info(f"Phase: {status['phase']}")
                    logger.info(f"Price: ${status['current_price']:.2f}")
                    logger.info(f"Unit: {status['current_unit']} (Peak: {status['peak_unit']})")
                    
                    if status['position']['has_position']:
                        pnl = status['position']['pnl']
                        pnl_icon = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
                        logger.info(f"Position: {status['position']['side']} | {pnl_icon} ${pnl:.2f}")
                    
                    if status['reset_count'] > 0:
                        total_return = ((status['position_allocation'] - status['initial_allocation']) / status['initial_allocation']) * 100
                        logger.info(f"🔄 Resets: {status['reset_count']} | Return: {total_return:.2f}%")
                    
                    logger.info("="*50)
                    
                    # Store for comparison
                    last_status = {
                        'current_unit': status['current_unit'],
                        'phase': status['phase'],
                        'pnl': status['position']['pnl']
                    }
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(5)
    
    async def shutdown(self, symbol: str):
        """Gracefully shutdown the strategy - IMPROVED VERSION"""
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
        
        # Ask about position closure - FIXED VERSION
        if self.strategy_manager.strategies.get(symbol):
            logger.warning("\nWARNING: Active position detected")
            
            try:
                # Use asyncio's run_in_executor to handle input properly
                import asyncio
                import sys
                
                print("Close position before shutdown? (y/n): ", end='', flush=True)
                
                # Read input in async-compatible way
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, sys.stdin.readline)
                response = response.strip().lower()
                
                if response == 'y' or response == 'yes':
                    logger.info("🔄 Closing position...")
                    await self.strategy_manager.stop_strategy(symbol, close_position=True)
                    logger.success("✅ Position closed successfully")
                else:
                    logger.warning("⚠️ Position left open - you must monitor manually!")
                    logger.info("Use: python main.py close ETH/USDC:USDC to close later")
                    
            except KeyboardInterrupt:
                logger.warning("\n⚠️ Interrupt received during shutdown")
                logger.warning("Position left open - use: python main.py close ETH/USDC:USDC")
            except Exception as e:
                logger.error(f"Error reading input: {e}")
                logger.warning("⚠️ Could not get user response")
                logger.warning("Position left open - use: python main.py close ETH/USDC:USDC")
        
        # Disconnect WebSocket
        if self.strategy_manager.ws_client.is_connected:
            await self.strategy_manager.ws_client.disconnect()
        
        logger.info("Shutdown complete")
        logger.info("=" * 60)


async def run_price_tracker(
    symbol: str = "ETH",
    unit_size: str = "2.0",
    duration_minutes: int = None
):
    """Run the WebSocket price tracker with unit tracking"""
    logger.info("=" * 60)
    logger.info(f"HyperTrader - Price Tracking with Unit Detection")
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Unit Size: ${unit_size}")
    logger.info(f"Duration: {duration_minutes} minutes" if duration_minutes else "Duration: Indefinite")
    logger.info("=" * 60)
    
    # Initialize WebSocket client
    ws_client = HyperliquidWebSocketClient(testnet=settings.hyperliquid_testnet)
    
    # Connect to WebSocket
    if not await ws_client.connect():
        logger.error("Failed to establish WebSocket connection")
        return False
    
    # Subscribe to trades with unit tracking
    if not await ws_client.subscribe_to_trades(symbol, Decimal(unit_size)):
        logger.error(f"Failed to subscribe to {symbol} trades")
        await ws_client.disconnect()
        return False
    
    # Run with optional timeout
    try:
        if duration_minutes:
            # Run for specified duration
            listen_task = asyncio.create_task(ws_client.listen())
            await asyncio.sleep(duration_minutes * 60)
            ws_client.is_connected = False
            await listen_task
        else:
            # Run indefinitely
            await ws_client.listen()
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Error in price tracker: {e}")
    finally:
        await ws_client.disconnect()
        
        # Log final state
        if symbol in ws_client.unit_trackers:
            tracker = ws_client.unit_trackers[symbol]
            logger.info("=" * 60)
            logger.info("Final State:")
            logger.info(f"Entry Price: ${tracker.entry_price:.2f}" if tracker.entry_price else "Entry Price: Not set")
            logger.info(f"Current Unit: {tracker.current_unit}")
            logger.info(f"Peak Unit: {tracker.peak_unit}")
            logger.info(f"Valley Unit: {tracker.valley_unit}")
            logger.info(f"Phase: {tracker.phase.value}")
            logger.info(f"Units from Peak: {tracker.get_units_from_peak()}")
            logger.info(f"Units from Valley: {tracker.get_units_from_valley()}")
            logger.info("=" * 60)
    
    return True


def check_positions():
    """Check current positions and balances"""
    logger.info("=" * 60)
    logger.info("Checking Positions and Balances")
    logger.info("=" * 60)
    
    try:
        # Initialize exchange client
        exchange = HyperliquidExchangeClient(testnet=settings.hyperliquid_testnet)
        
        # Get balance
        balance = exchange.get_balance("USDC")
        logger.info(f"Account Balance:")
        logger.info(f"  - Free: ${balance['free']:.2f}")
        logger.info(f"  - Used: ${balance['used']:.2f}")
        logger.info(f"  - Total: ${balance['total']:.2f}")
        
        # Check for positions
        symbols = ["ETH/USDC:USDC", "BTC/USDC:USDC", "SOL/USDC:USDC"]
        logger.info(f"\nActive Positions:")
        
        has_positions = False
        for sym in symbols:
            position = exchange.get_position(sym)
            if position:
                has_positions = True
                logger.info(f"  {sym}:")
                logger.info(f"    - Side: {position['side'].upper()}")
                logger.info(f"    - Size: {position['contracts']}")
                logger.info(f"    - Entry: ${position['entryPrice']:.2f}")
                logger.info(f"    - PnL: ${position['unrealizedPnl']:.2f}")
        
        if not has_positions:
            logger.info("  No active positions")
        
        logger.info("\n[SUCCESS] Check complete")
        return True
        
    except Exception as e:
        logger.error(f"[FAILED] Check failed: {e}")
        return False


def close_position(symbol: str):
    """Close a specific position"""
    logger.info(f"Closing position: {symbol}")
    
    try:
        # Initialize exchange client
        exchange = HyperliquidExchangeClient(testnet=settings.hyperliquid_testnet)
        
        # Get current position
        position = exchange.get_position(symbol)
        if not position:
            logger.info(f"No position found for {symbol}")
            return True
        
        # Close the position
        logger.info(f"Current position: {position['side']} {position['contracts']} contracts")
        result = exchange.close_position(symbol)
        
        if result:
            logger.info(f"[SUCCESS] Position closed successfully. Order ID: {result}")
            return True
        else:
            logger.error("Failed to close position")
            return False
            
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        return False


def run_tests(category: str = None):
    """Run test suite"""
    logger.info("=" * 60)
    logger.info("Running Tests")
    logger.info("=" * 60)
    
    if category:
        if category == "unit":
            test_path = "tests/unit"
        elif category == "integration":
            test_path = "tests/integration"
        elif category.startswith("verification"):
            stage = category.split(":")[-1] if ":" in category else None
            if stage:
                test_path = f"tests/verification/test_{stage}.py"
            else:
                test_path = "tests/verification"
        else:
            test_path = f"tests/{category}"
        logger.info(f"Running {category} tests from {test_path}")
    else:
        test_path = "tests"
        logger.info("Running all tests")
    
    # Run pytest
    result = subprocess.run(
        ["uv", "run", "pytest", test_path, "-v"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    if result.returncode == 0:
        logger.info("[SUCCESS] Tests passed")
    else:
        logger.error("[FAILED] Tests failed")
    
    return result.returncode == 0


async def main():
    """Main entry point with subcommands"""
    parser = argparse.ArgumentParser(
        description="HyperTrader - Advanced Hedging Strategy",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Trade command
    trade_parser = subparsers.add_parser("trade", help="Start trading strategy")
    trade_parser.add_argument("symbol", help="Trading symbol (e.g., ETH/USDC:USDC)")
    trade_parser.add_argument("position_size", type=float, help="Position size in USD")
    trade_parser.add_argument("unit_size", type=float, help="Unit size in USD")
    trade_parser.add_argument("--leverage", type=int, default=10, help="Leverage (default: 10)")
    trade_parser.add_argument("--mainnet", action="store_true", help="Use mainnet (default: testnet)")
    
    # Track command
    track_parser = subparsers.add_parser("track", help="Track prices with unit detection")
    track_parser.add_argument("--symbol", default="ETH", help="Symbol to track (default: ETH)")
    track_parser.add_argument("--unit-size", default="2.0", help="Unit size in USD (default: 2.0)")
    track_parser.add_argument("--duration", type=int, help="Duration in minutes (optional)")
    
    # Check command
    check_parser = subparsers.add_parser("check", help="Check positions and balances")
    
    # Close command
    close_parser = subparsers.add_parser("close", help="Close a position")
    close_parser.add_argument("symbol", help="Symbol to close (e.g., ETH/USDC:USDC)")
    
    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor running strategies")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("--category", help="Test category (unit, integration, verification:stage4)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Configure clean logging
    logger.remove()
    
    # Console logging - clean format for better readability
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Add file logging for trading commands - detailed for debugging
    if args.command in ["trade", "track"]:
        logger.add(
            "logs/hypertrader_{time:YYYYMMDD}.log",
            rotation="1 day",
            retention="7 days",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} | {message}"
        )
    
    # Execute command
    if args.command == "trade":
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
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            logger.info("\nReceived interrupt signal")
            asyncio.create_task(trader.shutdown(args.symbol))
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start trading
        await trader.start_trading(
            symbol=args.symbol,
            position_size_usd=Decimal(str(args.position_size)),
            unit_size=Decimal(str(args.unit_size)),
            leverage=args.leverage
        )
    
    elif args.command == "track":
        await run_price_tracker(
            symbol=args.symbol,
            unit_size=args.unit_size,
            duration_minutes=args.duration
        )
    
    elif args.command == "check":
        check_positions()
    
    elif args.command == "close":
        close_position(args.symbol)
    
    elif args.command == "monitor":
        # Import and run monitor tool
        from tools.monitor import monitor_strategy
        await monitor_strategy()
    
    elif args.command == "test":
        run_tests(args.category)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)