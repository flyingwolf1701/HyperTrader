import os
from decimal import Decimal
from typing import Dict, Any, Optional, List

from eth_account import Account
from eth_account.signers.local import LocalAccount
from loguru import logger

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils.signing import get_timestamp_ms


class HyperliquidSDK:
    """A wrapper for the Hyperliquid SDK to handle REST API calls."""

    def __init__(self, account: LocalAccount, is_mainnet: bool = False, vault_address: Optional[str] = None):
        """
        Initializes the Hyperliquid SDK wrapper.

        Args:
            account: The LocalAccount object with signing capability.
            is_mainnet: A boolean indicating whether to connect to the mainnet.
            vault_address: Optional vault address for sub-wallet trading.
        """
        self.account = account
        self.vault_address = vault_address
        # Use vault address if provided, otherwise use account address
        self.wallet_address = vault_address if vault_address else account.address
        self.is_mainnet = is_mainnet
        self.info: Optional[Info] = None
        self.exchange: Optional[Exchange] = None
        self.meta: Optional[Dict[str, Any]] = None

    async def initialize(self):
        """Initializes the SDK clients and fetches metadata."""
        network = "MAINNET" if self.is_mainnet else "TESTNET"
        logger.info(f"Initializing Hyperliquid REST SDK clients on {network}...")
        try:
            self.info = Info(self.is_mainnet)
            # Pass vault_address if we're using a sub-wallet
            if self.vault_address:
                self.exchange = Exchange(self.account, self.is_mainnet, vault_address=self.vault_address)
                logger.info(f"Using vault address: {self.vault_address[:8]}...")
            else:
                self.exchange = Exchange(self.account, self.is_mainnet)
            self.meta = self.info.meta()
            logger.success("Hyperliquid REST SDK initialized and metadata loaded.")
        except Exception as e:
            logger.error(f"Failed to initialize exchange metadata: {e}")

    def get_asset_meta(self, symbol: str) -> Optional[Dict]:
        """
        Retrieves the metadata for a specific asset from the cached universe data.

        Args:
            symbol: The asset symbol (e.g., "BTC", "SOL").

        Returns:
            A dictionary containing the asset's metadata, or None if not found.
        """
        if self.meta and "universe" in self.meta:
            for asset_info in self.meta["universe"]:
                if asset_info.get("name") == symbol:
                    return asset_info
        logger.warning(f"Metadata for asset '{symbol}' not found.")
        return None

    async def set_leverage(self, symbol: str, leverage: int, is_cross_margin: bool = True):
        """Set leverage for a specific asset."""
        if not self.exchange:
            logger.error("Exchange client not initialized.")
            return
        
        logger.info(f"Setting leverage for {symbol} to {leverage}x {'(Cross Margin)' if is_cross_margin else '(Isolated)'}")
        try:
            response = self.exchange.update_leverage(leverage, symbol, is_cross_margin)
            if response["status"] == "ok":
                logger.success(f"Successfully set leverage for {symbol} to {leverage}x")
            else:
                logger.error(f"Failed to set leverage for {symbol}: {response}")
        except Exception as e:
            logger.error(f"An error occurred while setting leverage for {symbol}: {e}")

    async def get_open_orders(self) -> List[Dict]:
        """Retrieve all open orders for the user."""
        if not self.info:
            logger.error("Info client not initialized.")
            return []
        
        try:
            open_orders = self.info.open_orders(self.wallet_address)
            return open_orders
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []

    async def place_order(self, order_data: Dict) -> Optional[Dict]:
        """
        Places an order on the exchange.

        Args:
            order_data: A dictionary containing order parameters.
        
        Returns:
            The response from the exchange, or None if an error occurred.
        """
        if not self.exchange:
            logger.error("Exchange client not initialized.")
            return None
        
        logger.info(f"Placing order: {order_data}")
        try:
            # Handle market orders - SDK requires a limit_px even for market orders
            limit_px = order_data.get("limit_px")
            if limit_px is None:
                # For market orders, use a very high/low price to ensure execution
                if order_data["is_buy"]:
                    limit_px = 1000000.0  # High price for market buy
                else:
                    limit_px = 0.01  # Low price for market sell

            response = self.exchange.order(
                order_data["coin"],
                order_data["is_buy"],
                order_data["sz"],
                limit_px,
                order_data["order_type"]
            )
            return response
        except Exception as e:
            logger.error(f"An error occurred while placing order: {e}")
            return None

    async def cancel_order(self, coin: str, order_id: str) -> Optional[Dict]:
        """
        Cancels a specific order.

        Args:
            coin: The asset symbol
            order_id: The order ID to cancel

        Returns:
            The response from the exchange
        """
        if not self.exchange:
            logger.error("Exchange client not initialized.")
            return None

        try:
            response = self.exchange.cancel(coin, order_id)
            return response
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return None

    async def cancel_all_orders(self):
        """Cancels all open orders for all assets."""
        if not self.exchange or not self.meta:
            logger.error("Exchange client or metadata not initialized.")
            return

        logger.warning("Cancelling all open orders...")
        try:
            open_orders = await self.get_open_orders()
            if not open_orders:
                logger.info("No open orders to cancel.")
                return

            cancellation_requests = []
            for order in open_orders:
                cancellation_requests.append({"coin": order["coin"], "oid": order["oid"]})

            if cancellation_requests:
                response = self.exchange.bulk_cancel(cancellation_requests)
                if response.get("status") == "ok":
                    logger.success("Successfully cancelled all open orders.")
                else:
                    logger.error(f"Failed to cancel all orders: {response}")
            else:
                logger.info("No open orders found to create cancellation requests.")

        except Exception as e:
            logger.error(f"An error occurred while cancelling all orders: {e}")

    async def get_user_state(self) -> Optional[Dict]:
        """Retrieve the user's current state, including positions and margin."""
        if not self.info:
            logger.error("Info client not initialized.")
            return None
        
        try:
            user_state = self.info.user_state(self.wallet_address)
            return user_state
        except Exception as e:
            logger.error(f"Failed to get user state: {e}")
            return None

