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

    def __init__(self, wallet_address: str, is_mainnet: bool = False):
        """
        Initializes the Hyperliquid SDK wrapper.

        Args:
            wallet_address: The user's wallet address.
            is_mainnet: A boolean indicating whether to connect to the mainnet.
        """
        self.use_testnet = use_testnet
        self.use_sub_wallet = use_sub_wallet
        
        # Set base URL based on network
        self.base_url = (
            "https://api.hyperliquid-testnet.xyz" if use_testnet 
            else "https://api.hyperliquid.xyz"
        )
        
        # Initialize wallet and clients
        self._initialize_clients()
        
    def _initialize_clients(self):
        """Initialize the SDK clients and wallet"""
        # Get credentials from environment variables
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        # Use the testnet API private key from .env
        private_key = os.getenv("HYPERLIQUID_TESTNET_API_PRIVATE_KEY")
        # Use the wallet address from .env
        self.main_wallet_address = os.getenv("HYPERLIQUID_WALLET_ADDRESS")
        # For now, sub-wallet is same as main (can be updated later if needed)
        self.sub_wallet_address = os.getenv("HYPERLIQUID_WALLET_ADDRESS")
        
        # Create LocalAccount from private key
        wallet = Account.from_key(private_key)
        
        # Initialize Info client for read operations
        self.info = Info(self.base_url, skip_ws=True)
        
        # Determine which wallet to use for trading
        if self.use_sub_wallet:
            # Trade on sub-wallet using vault_address
            self.exchange = Exchange(
                wallet=wallet,  # Pass LocalAccount object
                base_url=self.base_url,
                vault_address=self.sub_wallet_address
            )
            logger.info(f"Initialized with sub-wallet {self.sub_wallet_address[:8]}...")
        else:
            # Trade on main wallet
            self.exchange = Exchange(
                wallet=wallet,  # Pass LocalAccount object
                base_url=self.base_url
            )
            logger.info(f"Initialized with main wallet {self.main_wallet_address[:8]}...")
    
    def get_user_address(self) -> str:
        """
        Get the current trading wallet address.

        Returns:
            The wallet address being used for trading
        """
        return self.sub_wallet_address if self.use_sub_wallet else self.main_wallet_address
    
    def switch_wallet(self, use_sub_wallet: bool):
        """
        Switch between main wallet and sub-wallet.
        
        Args:
            use_sub_wallet: True to use sub-wallet, False for main wallet
        """
        if use_sub_wallet != self.use_sub_wallet:
            self.use_sub_wallet = use_sub_wallet
            self._initialize_clients()
    
    # ============================================================================
    # ACCOUNT INFORMATION
    # ============================================================================
    
    def get_balance(self) -> Balance:
        """
        Get account balance for the current wallet.
        
        Returns:
            Balance object with total value, margin used, and available balance
        """
        try:
            user_state = self.info.user_state(self.get_user_address())
            margin_summary = user_state.get("marginSummary", {})
            
            total_value = Decimal(str(margin_summary.get("accountValue", 0)))
            margin_used = Decimal(str(margin_summary.get("totalMarginUsed", 0)))
            
            return Balance(
                total_value=total_value,
                margin_used=margin_used,
                available=total_value - margin_used
            )
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
            Dictionary mapping symbol to OrderResult
        """
        results = {}
        positions = self.get_positions()
        
        for symbol, position in positions.items():
            logger.info(f"Closing {symbol} position...")
            results[symbol] = self.close_position(symbol)
        
        return results
    
    def place_stop_order(
        self,
        symbol: str,
        is_buy: bool,
        size: Decimal,
        trigger_price: Decimal,
        reduce_only: bool = True
    ) -> OrderResult:
        """
        Place a stop loss order that triggers at specified price.
        
        Args:
            symbol: Trading symbol
            is_buy: True for stop buy, False for stop sell
            size: Order size in base currency
            trigger_price: Price that triggers the stop
            reduce_only: If True, only reduces position (default True for stops)
            
        Returns:
            OrderResult with order details
        """
        try:
            # Round trigger price to tick size
            from .asset_config import round_to_tick
            rounded_trigger = round_to_tick(trigger_price, symbol)
            
            logger.info(
                f"Placing {'BUY' if is_buy else 'SELL'} stop order: "
                f"{size} {symbol} triggers @ ${rounded_trigger:.2f}"
            )
            logger.debug(f"Original trigger: ${trigger_price}, Rounded: ${rounded_trigger}, Tick size: ${get_tick_size(symbol)}")
            
            # Create stop loss order type
            # Use limit orders for all stops with proper tick sizing
            order_type = {
                "trigger": {
                    "triggerPx": float(rounded_trigger),
                    "isMarket": True, 
                    "tpsl": "sl"  # Stop loss type
                }
            }

            # Use the trigger price as the limit price
            limit_px = rounded_trigger
            
            # Get market info for proper decimal formatting
            market_info = self.get_market_info(symbol)
            sz_decimals = int(market_info.get("szDecimals", 4))
            
            # Round size to appropriate decimals
            rounded_size = round(float(size), sz_decimals)
            
            result = self.exchange.order(
                symbol, 
                is_buy, 
                rounded_size, 
                float(limit_px), 
                order_type, 
                reduce_only
            )
            
            # Parse result
            if result.get("status") == "ok":
                response = result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                
                if statuses and "resting" in statuses[0]:
                    resting = statuses[0]["resting"]
                    return OrderResult(
                        success=True,
                        order_id=str(resting.get("oid")),
                        filled_size=Decimal("0"),  # Not filled yet
                        average_price=rounded_trigger
                    )
                else:
                    return OrderResult(
                        success=False,
                        error_message=f"Unexpected response: {statuses}"
                    )
            else:
                error_msg = result.get("response", "Unknown error")
                return OrderResult(
                    success=False,
                    error_message=f"Stop order failed: {error_msg}"
                )
                
        except Exception as e:
            logger.error(f"Failed to place stop order: {e}")
            return OrderResult(
                success=False,
                error_message=str(e)
            )
    
    def place_stop_buy(
        self,
        symbol: str,
        size: Decimal,
        trigger_price: Decimal,
        limit_price: Optional[Decimal] = None,
        reduce_only: bool = False
    ) -> OrderResult:
        """
        Place a stop limit buy order that triggers when price rises to specified level.
        This is used for placing buy orders above current market price that wait for price to rise.
        
        Args:
            symbol: Trading symbol
            size: Order size in base currency
            trigger_price: Price that triggers the order (above current market)
            limit_price: Limit price for execution (if None, uses trigger_price)
            reduce_only: If True, only reduces position (usually False for entries)
            
        Returns:
            OrderResult with order details
        """
        try:
            # Round trigger price to tick size
            from .asset_config import round_to_tick
            rounded_trigger = round_to_tick(trigger_price, symbol)
            
            # Use trigger as limit if not specified
            if limit_price is None:
                limit_price = trigger_price
            rounded_limit = round_to_tick(limit_price, symbol)
            
            logger.info(
                f"Placing STOP LIMIT BUY order: "
                f"{size} {symbol} triggers @ ${rounded_trigger:.2f}, "
                f"limit @ ${rounded_limit:.2f}"
            )
            
            # Create stop buy order type (triggers when price rises)
            # Using "tp" (take profit) for buy orders that trigger when price goes UP
            order_type = {
                "trigger": {
                    "triggerPx": float(rounded_trigger),
                    "isMarket": True,
                    "tpsl": "tp"  # Take profit type (for buy orders, triggers when price rises above)
                }
            }
            
            # Get market info for proper decimal formatting
            market_info = self.get_market_info(symbol)
            sz_decimals = int(market_info.get("szDecimals", 4))
            
            # Round size to appropriate decimals
            rounded_size = round(float(size), sz_decimals)
            
            result = self.exchange.order(
                symbol, 
                True,  # is_buy = True
                rounded_size, 
                float(rounded_limit), 
                order_type, 
                reduce_only
            )
            
            # Parse result
            if result.get("status") == "ok":
                response = result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                
                if statuses and "resting" in statuses[0]:
                    resting = statuses[0]["resting"]
                    return OrderResult(
                        success=True,
                        order_id=str(resting.get("oid")),
                        filled_size=Decimal("0"),  # Not filled yet
                        average_price=rounded_limit
                    )
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
            logger.error(f"Failed to place limit order: {e}")
            return OrderResult(
                success=False,
                error_message=str(e)
            )
    
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.exchange.cancel(symbol, int(order_id))
            
            if result.get("status") == "ok":
                logger.info(f"Cancelled order {order_id} for {symbol}")
                return True
            else:
                logger.warning(f"Failed to cancel order: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    def modify_stop_order(
        self,
        order_id: int,
        symbol: str,
        is_buy: bool,
        size: Decimal,
        new_trigger_price: Decimal
    ) -> OrderResult:
        """
        Modifies an existing stop order by changing its trigger price.
        More efficient than cancel/replace for trailing stops.

        Args:
            order_id: The existing order ID to modify
            symbol: Trading pair symbol (e.g., 'ETH', 'BTC')
            is_buy: True for buy, False for sell
            size: Order size in base currency
            new_trigger_price: New trigger price for the stop order

        Returns:
            OrderResult with modification details
        """
        try:
            # Round trigger price to tick size
            from .asset_config import round_to_tick
            rounded_trigger = round_to_tick(new_trigger_price, symbol)

            logger.info(
                f"Modifying stop order {order_id}: New trigger @ ${rounded_trigger:.2f}"
            )

            # Create modified order type
            if is_buy:
                # For stop buys (trigger when price rises)
                order_type = {
                    "trigger": {
                        "triggerPx": float(rounded_trigger),
                        "isMarket": True,
                        "tpsl": "tp"  # Take profit for buys
                    }
                }
            else:
                # For stop sells (trigger when price falls)
                order_type = {
                    "trigger": {
                        "triggerPx": float(rounded_trigger),
                        "isMarket": True,
                        "tpsl": "sl"  # Stop loss for sells
                    }
                }

            # Get market info for proper decimal formatting
            market_info = self.get_market_info(symbol)
            sz_decimals = int(market_info.get("szDecimals", 4))

            # Round size to appropriate decimals
            rounded_size = round(float(size), sz_decimals)

            # Modify the order
            result = self.exchange.modify_order(
                order_id,
                {
                    "a": self.asset_id(symbol),
                    "b": is_buy,
                    "p": float(rounded_trigger),  # Use trigger as limit
                    "s": rounded_size,
                    "r": True,  # reduce_only for stops
                    "t": order_type
                }
            )

            # Parse result
            if result.get("status") == "ok":
                response = result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])

                if statuses and "resting" in statuses[0]:
                    modified_oid = statuses[0]["resting"]["oid"]
                    logger.info(f"✅ Successfully modified stop order {order_id} -> {modified_oid}")
                    return OrderResult(
                        success=True,
                        order_id=modified_oid,
                        error_message=None
                    )
                else:
                    error_msg = f"Unexpected response: {statuses}"
                    logger.error(error_msg)
                    return OrderResult(
                        success=False,
                        order_id=None,
                        error_message=error_msg
                    )
            else:
                error_msg = result.get("response", "Unknown error")
                logger.error(f"Failed to modify order: {error_msg}")
                return OrderResult(
                    success=False,
                    order_id=None,
                    error_message=error_msg
                )

        except Exception as e:
            logger.error(f"Error modifying stop order: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                error_message=f"Error modifying order: {e}"
            )

    def cancel_all_orders(self, symbol: str) -> int:
        """
        Cancel all open orders for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Number of orders cancelled
        """
        try:
            result = self.exchange.cancel_by_coin(symbol)
            
            if result.get("status") == "ok":
                response = result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                cancelled_count = len([s for s in statuses if "canceled" in s])
                logger.info(f"Cancelled {cancelled_count} orders for {symbol}")
                return cancelled_count
            else:
                logger.warning(f"Failed to cancel orders: {result}")
                return 0
                
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return 0
    
    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """
        Get all open orders.
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            List of open orders
        """
        try:
            user_state = self.info.user_state(self.get_user_address())
            open_orders = user_state.get("openOrders", [])
            
            if symbol:
                open_orders = [o for o in open_orders if o.get("coin") == symbol]
            
            return open_orders
            
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []