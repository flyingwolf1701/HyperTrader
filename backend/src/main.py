"""
HyperTrader - Long-Biased Grid Trading Bot
Main entry point with CLI interface.
"""

import asyncio
import argparse
from decimal import Decimal
from pathlib import Path
import sys
from loguru import logger

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.exchange.wallet_config import WalletConfig
from src.exchange.hyperliquid_sdk import HyperliquidClient
from src.exchange.hyperliquid_sdk_websocket import HyperliquidSDKWebSocketClient
from src.strategy.grid_strategy import GridTradingStrategy
from src.strategy.data_models import StrategyConfig


def setup_logging():
    """Configure logging with loguru."""
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "logs/hypertrader_{time}.log",
        rotation="1 day",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level="DEBUG"
    )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="HyperTrader - Long-Biased Grid Trading Bot",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Required arguments
    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Trading symbol (e.g., ETH, BTC, SOL)"
    )

    parser.add_argument(
        "--unit-size",
        type=float,
        required=True,
        help="USD amount per unit (e.g., 1.0 for $1 moves on SOL, 100 for $100 moves on BTC)"
    )

    parser.add_argument(
        "--position-size",
        type=float,
        required=True,
        help="Position value in USD (wallet allocation)"
    )

    parser.add_argument(
        "--leverage",
        type=int,
        required=True,
        help="Leverage multiplier (e.g., 10, 20, 40)"
    )

    # Optional arguments
    parser.add_argument(
        "--strategy",
        type=str,
        default="long",
        choices=["long"],
        help="Strategy type (currently only 'long' is implemented)"
    )

    parser.add_argument(
        "--testnet",
        action="store_true",
        default=True,
        help="Use testnet (default: True)"
    )

    parser.add_argument(
        "--mainnet",
        action="store_true",
        help="Use mainnet (overrides --testnet)"
    )

    parser.add_argument(
        "--wallet",
        type=str,
        default="main",
        choices=["main", "sub"],
        help="Which wallet to use for trading"
    )

    args = parser.parse_args()

    # Handle mainnet flag
    if args.mainnet:
        args.testnet = False

    return args


async def main():
    """Main entry point for the trading bot."""
    # Setup logging
    setup_logging()

    # Parse arguments
    args = parse_arguments()

    logger.info("=" * 60)
    logger.info("HyperTrader - Long-Biased Grid Trading Bot")
    logger.info("=" * 60)
    logger.info(f"Symbol: {args.symbol}")
    logger.info(f"Unit Size: ${args.unit_size}")
    logger.info(f"Position Size: ${args.position_size}")
    logger.info(f"Leverage: {args.leverage}x")
    logger.info(f"Total Position Value: ${args.position_size * args.leverage}")
    logger.info(f"Network: {'TESTNET' if args.testnet else 'MAINNET'}")
    logger.info(f"Wallet: {args.wallet}")
    logger.info("=" * 60)

    try:
        # Load wallet configuration
        config = WalletConfig.from_env()
        logger.info("Wallet configuration loaded successfully")

        # Initialize exchange client
        client = HyperliquidClient(
            config=config,
            wallet_type=args.wallet,
            use_testnet=args.testnet
        )
        logger.info(f"Connected to Hyperliquid {'testnet' if args.testnet else 'mainnet'}")

        # Initialize WebSocket client
        websocket = HyperliquidSDKWebSocketClient(
            testnet=args.testnet,
            user_address=client.get_user_address()
        )

        # Connect WebSocket
        if not await websocket.connect():
            logger.error("Failed to connect to WebSocket")
            return

        # Start WebSocket listener BEFORE initializing strategy
        # This ensures price updates and fills are captured from the start
        websocket_task = asyncio.create_task(websocket.listen())
        logger.info("WebSocket listener started")

        # Create strategy configuration
        strategy_config = StrategyConfig(
            symbol=args.symbol,
            leverage=args.leverage,
            wallet_allocation=Decimal(str(args.position_size)),
            unit_size=Decimal(str(args.unit_size)),
            testnet=args.testnet,
            wallet_type=args.wallet
        )

        # Initialize strategy
        strategy = GridTradingStrategy(
            config=strategy_config,
            client=client,
            websocket=websocket
        )

        # Initialize the strategy (establish position and grid)
        if not await strategy.initialize():
            logger.error("Failed to initialize strategy")
            websocket_task.cancel()
            try:
                await websocket_task
            except asyncio.CancelledError:
                pass
            await websocket.disconnect()
            return

        # Run the strategy
        strategy_task = asyncio.create_task(strategy.run())

        # Wait for strategy completion
        await strategy_task

        # Cancel websocket task
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass

        # Disconnect websocket
        await websocket.disconnect()

    except KeyboardInterrupt:
        logger.warning("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        logger.info("HyperTrader shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)