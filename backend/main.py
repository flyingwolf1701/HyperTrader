"""
HyperTrader Backend - Main Entry Point
Stages 1-3: WebSocket + Unit Tracking + Exchange Integration
"""
import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from core import HyperliquidWebSocketClient
from exchange import HyperliquidExchangeClient
from utils import settings


async def run_price_tracker(
    symbol: str = "ETH",
    unit_size: str = "2.0",
    duration_minutes: int = None
):
    """
    Run the WebSocket price tracker with unit tracking.
    
    Args:
        symbol: Cryptocurrency symbol to track
        unit_size: Price movement that constitutes one unit (in USD)
        duration_minutes: Optional duration to run (None = indefinite)
    """
    # Set up logging
    logger.add(
        "logs/price_tracker.log",
        rotation="1 day",
        retention="7 days",
        level=settings.log_level
    )
    
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


def check_exchange_connection():
    """Check exchange connection and display account info"""
    logger.info("=" * 60)
    logger.info("Checking Exchange Connection")
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
        symbols = ["ETH/USDC:USDC", "BTC/USDC:USDC"]
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
        
        logger.success("\n✅ Exchange connection successful")
        return True
        
    except Exception as e:
        logger.error(f"❌ Exchange connection failed: {e}")
        return False


async def main():
    """Main entry point for HyperTrader Backend"""
    import argparse
    
    parser = argparse.ArgumentParser(description="HyperTrader - Automated Trading System")
    parser.add_argument("--mode", choices=["track", "exchange", "demo"], default="track",
                       help="Operation mode: track (price tracking), exchange (check connection), demo (capabilities)")
    parser.add_argument("--symbol", default="ETH", help="Symbol to track (default: ETH)")
    parser.add_argument("--unit-size", default="2.0", help="Unit size in USD (default: 2.0)")
    parser.add_argument("--duration", type=int, help="Duration in minutes (optional)")
    
    args = parser.parse_args()
    
    if args.mode == "track":
        # Run price tracker
        await run_price_tracker(
            symbol=args.symbol,
            unit_size=args.unit_size,
            duration_minutes=args.duration
        )
    elif args.mode == "exchange":
        # Check exchange connection
        check_exchange_connection()
    elif args.mode == "demo":
        # Run trading demo
        from demo_trading import demonstrate_trading
        demonstrate_trading()


if __name__ == "__main__":
    asyncio.run(main())