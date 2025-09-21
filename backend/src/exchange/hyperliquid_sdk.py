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
            The response from the exchange, or None if an error occurred.
        """
        if not self.exchange:
            logger.error("Exchange client not initialized.")
            return None
        
        logger.info(f"Placing order: {order_data}")
        try:
            response = self.exchange.order(
                order_data["coin"],
                order_data["is_buy"],
                order_data["sz"],
                order_data["limit_px"],
                order_data["order_type"]
            )
            return response
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
            
            # Create trigger order (NOT a TP/SL order, since we're opening/increasing position)
            # This is a regular stop order that triggers when price rises
            order_type = {
                "trigger": {
                    "triggerPx": float(rounded_trigger),
                    "isMarket": False  # Execute as limit when triggered
                    # NOTE: Removed "tpsl" parameter - TP/SL orders are only for closing positions
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
            logger.error(f"Failed to get user state: {e}")
            return None

