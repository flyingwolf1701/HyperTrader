"""
Strategy runner that can be called from both CLI and API
"""
import asyncio
import os
from decimal import Decimal
from typing import Dict, Optional
from loguru import logger
from eth_account import Account

from core.config import StrategyConfig
from exchange.websocket_client import HyperliquidSDKClient
from exchange.hyperliquid_sdk import HyperliquidSDK
from strategy.v10_strategy_manager import V10StrategyManager


class StrategyRunner:
    """Manages strategy lifecycle for both CLI and API usage"""

    def __init__(self, config: StrategyConfig):
        """Initialize the strategy runner with configuration"""
        self.config = config
        self.strategy_manager: Optional[V10StrategyManager] = None
        self.ws_client: Optional[HyperliquidSDKClient] = None
        self.exchange_sdk: Optional[HyperliquidSDK] = None
        self.running = False
        self.tasks = []

    async def initialize(self):
        """Initialize all components"""
        logger.info(f"Initializing strategy for {self.config.symbol}")

        # Ensure environment variables are loaded
        from pathlib import Path
        from dotenv import load_dotenv

        # Try to find .env file in various locations
        if Path('../../.env').exists():
            load_dotenv('../../.env')  # From core directory
        elif Path('../.env').exists():
            load_dotenv('../.env')  # From src directory
        elif Path('.env').exists():
            load_dotenv('.env')  # From backend directory

        # Load wallet and addresses from environment
        # Use the API wallet private key for signing transactions
        private_key = os.getenv("HYPERLIQUID_TESTNET_API_PRIVATE_KEY")
        if not private_key:
            raise ValueError("HYPERLIQUID_TESTNET_API_PRIVATE_KEY environment variable not set")

        # Main wallet address that we're trading for
        main_wallet_address = os.getenv("HYPERLIQUID_WALLET_ADDRESS")
        if not main_wallet_address:
            raise ValueError("HYPERLIQUID_WALLET_ADDRESS environment variable not set")

        # API wallet address (for reference/logging)
        api_wallet_address = os.getenv("HYPERLIQUID_TESTNET_API_ADDRESS")

        # Create account from API wallet private key
        account = Account.from_key(private_key)

        # When using an API wallet to trade for the main wallet:
        # - The API wallet (account) signs the transactions
        # - We don't use vault_address (that's only for sub-accounts)
        # - The wallet_address tells the SDK which wallet we're tracking
        if self.config.wallet == "long":
            user_address = main_wallet_address
            vault_address = None  # No vault for main wallet trading
            logger.info(f"Trading for main wallet: {main_wallet_address[:8]}...")
            logger.info(f"Using API wallet for signing: {api_wallet_address[:8] if api_wallet_address else account.address[:8]}...")
        else:
            # For other wallet types, adjust as needed
            user_address = main_wallet_address
            vault_address = None
            logger.info(f"Using main wallet: {main_wallet_address[:8]}...")

        # Mask the wallet address for security
        masked_address = f"{user_address[:6]}...{user_address[-4:]}" if user_address else "Unknown"
        logger.success(f"Wallet loaded: {masked_address}")

        # Initialize REST API Client
        # Pass the wallet_address to track the correct wallet's state
        self.exchange_sdk = HyperliquidSDK(
            account=account,
            is_mainnet=not self.config.testnet,
            vault_address=vault_address,
            wallet_address=user_address
        )
        await self.exchange_sdk.initialize()

        # Get asset metadata
        asset_meta = self.exchange_sdk.get_asset_meta(self.config.symbol)
        if not asset_meta:
            raise ValueError(f"Could not retrieve metadata for {self.config.symbol}")

        asset_config = {
            "size_decimals": asset_meta.get("szDecimals", 2)
        }

        # Initialize v10 Strategy Manager
        self.strategy_manager = V10StrategyManager(
            exchange=self.exchange_sdk,
            asset=self.config.symbol,
            wallet_allocation=self.config.position_size,
            leverage=self.config.leverage,
            unit_size_usd=self.config.unit_size,
            asset_config=asset_config
        )

        # Initialize WebSocket Client with the correct wallet address
        self.ws_client = HyperliquidSDKClient(account=account, testnet=self.config.testnet, wallet_address=user_address)
        await self.ws_client.connect()

        logger.success("All components initialized")

    async def start(self):
        """Start the trading strategy"""
        if self.running:
            logger.warning("Strategy already running")
            return {"status": "error", "message": "Strategy already running"}

        try:
            await self.initialize()

            # Price tracking
            self.current_price = None

            def update_price(price: Decimal):
                self.current_price = price
                logger.debug(f"Price updated: ${price}")

            def get_current_price():
                return self.current_price

            # Setup callbacks
            async def handle_order_fill(order_id: str, filled_price: Decimal, filled_size: Decimal):
                logger.success(f"Order {order_id} filled at ${filled_price}")
                await self.strategy_manager.handle_order_fill(order_id, filled_price, filled_size)

            # Subscribe to data feeds
            await self.ws_client.subscribe_to_trades(
                symbol=self.config.symbol,
                price_callback=update_price
            )

            await self.ws_client.subscribe_to_user_events(
                fill_callback=lambda oid, price, size: handle_order_fill(oid, price, size),
                order_callback=lambda data: logger.info(f"Order update: {data}"),
                cancel_callback=lambda data: logger.warning(f"Order cancelled: {data}")
            )

            # Start WebSocket listener
            ws_task = self.ws_client.start_listening()
            self.tasks.append(ws_task)

            # Start strategy task
            strategy_task = asyncio.create_task(self._run_strategy(get_current_price))
            self.tasks.append(strategy_task)

            self.running = True
            logger.success(f"Strategy started for {self.config.symbol}")

            return {
                "status": "success",
                "message": f"Strategy started for {self.config.symbol}",
                "config": self.config.to_dict()
            }

        except Exception as e:
            logger.error(f"Failed to start strategy: {e}")
            return {"status": "error", "message": str(e)}

    async def _run_strategy(self, get_current_price):
        """Main strategy loop"""
        logger.info("Starting v10 strategy loop...")

        # Wait for price feed or fetch directly
        max_attempts = 10
        for attempt in range(max_attempts):
            await asyncio.sleep(2)
            current_price = get_current_price()

            if not current_price:
                # Try to get price directly from REST API
                logger.info(f"Waiting for price feed... attempt {attempt + 1}/{max_attempts}")

                # Fetch price using the Info API
                try:
                    if self.exchange_sdk and self.exchange_sdk.info:
                        # Get the mid price for the asset
                        mids = self.exchange_sdk.info.all_mids()
                        if mids and self.config.symbol in mids:
                            current_price = Decimal(str(mids[self.config.symbol]))
                            self.current_price = current_price
                            logger.info(f"Fetched price from REST API: ${current_price}")
                except Exception as e:
                    logger.debug(f"Could not fetch price from REST: {e}")

            if current_price:
                break

        # Initialize position
        if current_price:
            logger.info(f"Initializing position at price: ${current_price}")
            success = await self.strategy_manager.initialize_position(current_price)
            if not success:
                logger.error("Failed to initialize strategy position")
                return
        else:
            logger.error(f"No price available after {max_attempts} attempts")
            return

        # Main loop
        while self.running:
            try:
                await asyncio.sleep(10)

                current_price = get_current_price()
                if current_price:
                    await self.strategy_manager.update_grid_sliding(current_price)

                    status = self.strategy_manager.get_status()
                    logger.info(
                        f"Strategy | Price: ${current_price:.2f} | "
                        f"State: {status['grid_state']} | Orders: {status['order_composition']}"
                    )

            except asyncio.CancelledError:
                logger.warning("Strategy task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in strategy loop: {e}")
                await asyncio.sleep(30)

    async def stop(self):
        """Stop the trading strategy"""
        if not self.running:
            return {"status": "error", "message": "Strategy not running"}

        logger.warning("Stopping strategy...")
        self.running = False

        # Cancel tasks
        for task in self.tasks:
            task.cancel()

        # Disconnect WebSocket
        if self.ws_client:
            await self.ws_client.disconnect()

        # Cancel all orders
        if self.exchange_sdk:
            await self.exchange_sdk.cancel_all_orders()

        logger.success("Strategy stopped")
        return {"status": "success", "message": "Strategy stopped"}

    async def get_status(self) -> Dict:
        """Get current strategy status"""
        if not self.running or not self.strategy_manager:
            return {"status": "not_running"}

        return self.strategy_manager.get_status()


async def run_strategy(config: StrategyConfig):
    """Convenience function to run strategy (for CLI)"""
    runner = StrategyRunner(config)

    try:
        # Start strategy
        result = await runner.start()
        if result["status"] != "success":
            logger.error(f"Failed to start: {result['message']}")
            return

        # Keep running until interrupted
        await asyncio.gather(*runner.tasks)

    except KeyboardInterrupt:
        logger.warning("Shutdown signal received")
    finally:
        await runner.stop()