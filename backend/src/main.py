"""
HyperTrader v10 - Command Line Interface
Supports the command format:
uv run python src/main.py --symbol SOL --wallet long --unit-size 0.5 --position-size 2000 --leverage 20 --testnet
"""
import asyncio
import argparse
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

from core.config import StrategyConfig
from core.strategy_runner import run_strategy

# Load environment variables
load_dotenv()


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="HyperTrader v10 - Long-Biased Grid Trading Strategy"
    )

    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Trading symbol (e.g., SOL, BTC, ETH)"
    )

    parser.add_argument(
        "--wallet",
        type=str,
        required=True,
        help="Wallet type (e.g., long)"
    )

    parser.add_argument(
        "--unit-size",
        type=float,
        required=True,
        help="Price movement per unit in USD (e.g., 0.5)"
    )

    parser.add_argument(
        "--position-size",
        type=float,
        required=True,
        help="Total USD amount to allocate (e.g., 2000)"
    )

    parser.add_argument(
        "--leverage",
        type=int,
        required=True,
        help="Leverage multiplier (e.g., 20)"
    )

    parser.add_argument(
        "--testnet",
        action="store_true",
        default=False,
        help="Use testnet (default: False for mainnet)"
    )

    parser.add_argument(
        "--mainnet",
        action="store_true",
        default=False,
        help="Use mainnet explicitly"
    )

    return parser.parse_args()


async def main():
    """Main entry point for CLI"""
    # Parse command-line arguments
    args = parse_arguments()

    # Setup dynamic logging with strategy, coin, and datetime
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_filename = f"../logs/{args.wallet}_{args.symbol}_log_{timestamp}.txt"

    # Create logs directory if it doesn't exist
    import os
    os.makedirs("../logs", exist_ok=True)

    logger.add(log_filename, rotation="10 MB", level="DEBUG")

    # Handle testnet/mainnet flags
    if args.mainnet:
        args.testnet = False
    elif not args.testnet:
        # If neither flag is set, default to testnet for safety
        args.testnet = True
        logger.warning("No network specified, defaulting to TESTNET for safety")

    # Create configuration from arguments
    try:
        config = StrategyConfig.from_args(args)
        config.validate()
    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        return

    # Log configuration
    logger.info("=" * 50)
    logger.info("HyperTrader v10 Strategy Configuration")
    logger.info("=" * 50)
    logger.info(f"Symbol: {config.symbol}")
    logger.info(f"Wallet: {config.wallet}")
    logger.info(f"Unit Size: ${config.unit_size}")
    logger.info(f"Position Size: ${config.position_size}")
    logger.info(f"Leverage: {config.leverage}x")
    logger.info(f"Network: {'TESTNET' if config.testnet else 'MAINNET'}")
    logger.info(f"Total Exposure: ${config.position_size * config.leverage}")
    logger.info("=" * 50)

    # Confirmation prompt for mainnet
    if not config.testnet:
        logger.warning("⚠️  You are about to trade on MAINNET with real funds!")
        response = input("Type 'YES' to confirm: ")
        if response != "YES":
            logger.info("Mainnet trading cancelled")
            return

    # Run the strategy
    try:
        await run_strategy(config)
    except KeyboardInterrupt:
        logger.info("Strategy terminated by user")
    except Exception as e:
        logger.error(f"Strategy error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")