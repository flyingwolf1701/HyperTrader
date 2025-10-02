"""
Hyperliquid SDK Wrapper
Provides a clean interface to the Hyperliquid exchange
"""

from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass

from loguru import logger
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils.signing import Account

from .wallet_config import WalletConfig, WalletType

@dataclass
class Position:
    """Represents an open position"""
    symbol: str
    is_long: bool
    size: Decimal
    entry_price: Decimal
    unrealized_pnl: Decimal
    margin_used: Decimal
    
    @property
    def side(self) -> str:
        return "LONG" if self.is_long else "SHORT"


@dataclass
class Balance:
    """Represents account balance"""
    total_value: Decimal
    margin_used: Decimal
    available: Decimal


@dataclass
class OrderResult:
    """Represents the result of an order"""
    success: bool
    order_id: Optional[str] = None
    filled_size: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    error_message: Optional[str] = None


class HyperliquidClient:
    """
    Main client for interacting with Hyperliquid exchange.
    Handles both main wallet and sub-wallet operations.
    """
    
    def __init__(self, config: WalletConfig, wallet_type: WalletType = "main", mainnet: bool = False):
        """
        Initialize the Hyperliquid client with explicit configuration.

        Args:
            config: WalletConfig object containing credentials and addresses
            wallet_type: Which wallet to use for trading ("main", "sub", "long", "short", "hedge")
            mainnet: Whether to use mainnet (True) or testnet (False) - matches SDK convention
        """
        self.config = config
        self.wallet_type = wallet_type
        self.mainnet = mainnet

        # Set base URL based on network
        self.base_url = (
            "https://api.hyperliquid.xyz" if mainnet
            else "https://api.hyperliquid-testnet.xyz"
        )

        # Get the active wallet address based on type
        self.active_wallet_address = config.get_wallet_address(wallet_type)

        # Initialize wallet and clients
        self._initialize_clients()
        
    def _initialize_clients(self):
        """Initialize the SDK clients with provided configuration"""
        # Create LocalAccount from private key
        wallet = Account.from_key(self.config.private_key)

        # Initialize Info client for read operations
        self.info = Info(self.base_url, skip_ws=True)

        # Determine vault_address parameter based on wallet type
        # If using sub wallet, we need to pass it as vault_address
        # If using main wallet, we don't pass vault_address
        is_using_sub = self.active_wallet_address == self.config.sub_wallet_address

        if is_using_sub:
            # Trade on sub-wallet using vault_address parameter
            self.exchange = Exchange(
                wallet=wallet,
                base_url=self.base_url,
                vault_address=self.active_wallet_address
            )
            logger.info(f"Initialized with {self.wallet_type} wallet (sub): {self.active_wallet_address[:8]}...")
        else:
            # Trade on main wallet (no vault_address needed)
            self.exchange = Exchange(
                wallet=wallet,
                base_url=self.base_url
            )
            logger.info(f"Initialized with {self.wallet_type} wallet (main): {self.active_wallet_address[:8]}...")
    
    def get_user_address(self) -> str:
        """
        Get the current trading wallet address.

        Returns:
            The wallet address being used for trading
        """
        return self.active_wallet_address
    
    def switch_wallet(self, wallet_type: WalletType):
        """
        Switch to a different wallet type.

        Args:
            wallet_type: The wallet type to switch to
        """
        if wallet_type != self.wallet_type:
            self.wallet_type = wallet_type
            self.active_wallet_address = self.config.get_wallet_address(wallet_type)
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
            logger.error(f"Failed to get balance: {e}")
            raise
    
    def get_positions(self) -> Dict[str, Position]:
        """
        Get all open positions for the current wallet.
        
        Returns:
            Dictionary mapping symbol to Position object
        """
        try:
            user_state = self.info.user_state(self.get_user_address())
            positions = {}
            
            for asset_position in user_state.get("assetPositions", []):
                position_data = asset_position.get("position", {})
                szi = float(position_data.get("szi", 0))
                
                if szi != 0:  # Has an open position
                    symbol = position_data.get("coin")
                    positions[symbol] = Position(
                        symbol=symbol,
                        is_long=szi > 0,
                        size=Decimal(str(abs(szi))),
                        entry_price=Decimal(str(position_data.get("entryPx", 0))),
                        unrealized_pnl=Decimal(str(asset_position.get("unrealizedPnl", 0))),
                        margin_used=Decimal(str(position_data.get("marginUsed", 0)))
                    )
            
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a specific symbol.
        
        Args:
            symbol: Trading symbol (e.g., "ETH")
            
        Returns:
            Position object if exists, None otherwise
        """
        positions = self.get_positions()
        return positions.get(symbol)
    
    # ============================================================================
    # MARKET DATA
    # ============================================================================
    
    def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current market price for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "ETH")
            
        Returns:
            Current mid-market price
        """
        try:
            all_mids = self.info.all_mids()
            price = all_mids.get(symbol, 0)
            if price == 0:
                raise ValueError(f"Could not get price for {symbol}")
            return Decimal(str(price))
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            raise
    
    def get_market_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get market metadata for a symbol including tickSize and szDecimals.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Market information including tickSize, szDecimals, etc.
        """
        try:
            meta = self.info.meta()
            # The asset details are in the 'universe' key
            assets = meta.get("universe", [])
            
            for asset in assets:
                if asset.get("name") == symbol:
                    return asset
            
            raise ValueError(f"Market info not found for {symbol}")
        except Exception as e:
            logger.error(f"Failed to get market info: {e}")
            raise
    
    # ============================================================================
    # TRADING OPERATIONS
    # ============================================================================
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a symbol.

        Args:
            symbol: Trading symbol
            leverage: Leverage multiplier (e.g., 10 for 10x)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get max leverage from market info
            market_info = self.get_market_info(symbol)
            max_allowed = int(market_info.get("maxLeverage", 20))  # Default to 20x if not specified
            if leverage > max_allowed:
                logger.warning(f"Requested {leverage}x exceeds max {max_allowed}x for {symbol}, using max")
                leverage = max_allowed

            logger.info(f"Setting leverage to {leverage}x for {symbol}")

            # Try to set the leverage with cross margin
            result = self.exchange.update_leverage(
                leverage=leverage,
                name=symbol,
                is_cross=True  # Use cross margin
            )
    
            # logger.info(f"RAW LEVERAGE RESPONSE: {result}")

            if result.get("status") == "ok":
                logger.info(f"✅ Successfully set leverage to {leverage}x for {symbol}")
                return True
            else:
                error_msg = result.get("response", "Unknown error")
                logger.error(f"❌ Failed to set {leverage}x leverage: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            return False
    
    def calculate_position_size(self, symbol: str, usd_amount: Decimal) -> Decimal:
        """
        Calculate position size in base currency from USD amount.
        
        Args:
            symbol: Trading symbol
            usd_amount: Position size in USD
            
        Returns:
            Position size in base currency, properly rounded
        """
        current_price = self.get_current_price(symbol)
        
        # Get market info for decimals
        market_info = self.get_market_info(symbol)
        sz_decimals = int(market_info["szDecimals"])
        
        # Calculate and round to appropriate decimals
        size = usd_amount / current_price
        return Decimal(str(round(float(size), sz_decimals)))
    
    def open_position(
        self, 
        symbol: str, 
        usd_amount: Decimal,
        is_long: bool = True,
        leverage: Optional[int] = None,
        slippage: float = 0.01
    ) -> OrderResult:
        """
        Open a new position.
        
        Args:
            symbol: Trading symbol (e.g., "ETH")
            usd_amount: Position size in USD
            is_long: True for long, False for short
            leverage: Optional leverage to set before opening
            slippage: Maximum slippage tolerance (default 1%)
            
        Returns:
            OrderResult with execution details
        """
        try:
            # Validate and set leverage if specified
            if leverage:
                market_info = self.get_market_info(symbol)
                # TODO: Why is max leverage hardcoded to 20?
                max_lev = int(market_info.get("maxLeverage", 20))
                if not (1 <= leverage <= max_lev):
                    return OrderResult(
                        success=False,
                        error_message=f"Invalid leverage {leverage} for {symbol}. Max allowed: {max_lev}"
                    )
                self.set_leverage(symbol, leverage)
            
            # Calculate position size in coins from USD amount
            # We need to convert USD to coin amount based on current price for the order

            position_size_coin = self.calculate_position_size(symbol, usd_amount)
            
            logger.info(
                f"Opening {'LONG' if is_long else 'SHORT'} position: "
                f"{position_size_coin} {symbol} (${usd_amount})"
            )
            
            # Place market order
            result = self.exchange.market_open(
                name=symbol,
                is_buy=is_long,
                sz=float(position_size_coin),
                px=None,  # Let SDK calculate
                slippage=slippage
            )
            
            # logger.info(f"RAW OPEN POSITION RESPONSE: {result}")

            # Parse result
            if result.get("status") == "ok":
                response = result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                
                if statuses and "filled" in statuses[0]:
                    filled = statuses[0]["filled"]
                    return OrderResult(
                        success=True,
                        order_id=str(filled.get("oid")),
                        filled_size=Decimal(str(filled.get("totalSz", 0))),
                        average_price=Decimal(str(filled.get("avgPx", 0)))
                    )
                elif statuses and "error" in statuses[0]:
                    return OrderResult(
                        success=False,
                        error_message=statuses[0]["error"]
                    )
            
            return OrderResult(
                success=False,
                error_message=f"Unexpected response: {result}"
            )
            
        except Exception as e:
            logger.error(f"Failed to open position: {e}")
            return OrderResult(
                success=False,
                error_message=str(e)
            )
    
    def close_position(self, symbol: str, slippage: float = 0.01) -> OrderResult:
        """
        Close an existing position.
        
        Args:
            symbol: Trading symbol
            slippage: Maximum slippage tolerance
            
        Returns:
            OrderResult with execution details
        """
        try:
            # Get current position
            position = self.get_position(symbol)
            if not position:
                return OrderResult(
                    success=False,
                    error_message=f"No position to close for {symbol}"
                )
            
            logger.info(
                f"Closing {position.side} position: "
                f"{position.size} {symbol}"
            )
            
            result = self.exchange.market_open(
                name=symbol,
                is_buy=not position.is_long, # Opposite side to close
                sz=float(position.size),
                px=None,
                slippage=slippage
            )
            
            # logger.info(f"RAW CLOSE POSITION RESPONSE: {result}")
            
            # Parse result
            if result.get("status") == "ok":
                response = result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                
                if statuses and "filled" in statuses[0]:
                    filled = statuses[0]["filled"]
                    return OrderResult(
                        success=True,
                        order_id=str(filled.get("oid")),
                        filled_size=Decimal(str(filled.get("totalSz", 0))),
                        average_price=Decimal(str(filled.get("avgPx", 0)))
                    )
            
            return OrderResult(
                success=False,
                error_message=f"Failed to close: {result}"
            )
            
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return OrderResult(
                success=False,
                error_message=str(e)
            )
    
    def close_all_positions(self) -> Dict[str, OrderResult]:
        """
        Close all open positions.
        
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
            # Get tick size from market info and round trigger price
            # TODO: I don't like that these values are hard coded. we should be able to get the tick_size and szDecimals from the coin meta.
            market_info = self.get_market_info(symbol)
            tick_size = Decimal(str(market_info.get("szDecimals", 4)))
            tick_size = Decimal("10") ** -tick_size  # Convert decimals to tick size

            # Round to tick size
            multiplier = trigger_price / tick_size
            rounded_trigger = multiplier.quantize(Decimal('1'), rounding='ROUND_HALF_UP') * tick_size
            
            logger.info(
                f"Placing {'BUY' if is_buy else 'SELL'} stop order: "
                f"{size} {symbol} triggers @ ${rounded_trigger:.2f}"
            )
            logger.info(f"Original trigger: ${trigger_price}, Rounded: ${rounded_trigger}, Tick size: ${tick_size}")
            
            # Create stop loss order type
            # Use limit orders for all stops with proper tick sizing
            
            order_type = {
                "trigger": {
                    "triggerPx": float(rounded_trigger),
                    "isMarket": True, 
                    "tpsl": "sl"
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
            
            # logger.info(f"RAW STOP ORDER RESPONSE: {result}")

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
                        filled_size=Decimal("0"),
                        average_price=Decimal(str(rounded_trigger))
                    )
                elif statuses and "error" in statuses[0]:
                    error_msg = statuses[0]["error"]
                    return OrderResult(success=False, error_message=error_msg)
                else:
                    return OrderResult(success=False, error_message=f"Unexpected response: {statuses}")

            else:
                error_msg = result.get("response", "Unknown error")
                return OrderResult(success=False, error_message=f"Stop order failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to place stop order: {e}", exc_info=True)
            return OrderResult(success=False, error_message=str(e))
    
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
            # Get tick size from market info and round prices
            market_info = self.get_market_info(symbol)
            tick_size = Decimal(str(market_info.get("szDecimals", 4)))
            tick_size = Decimal("10") ** -tick_size  # Convert decimals to tick size

            # Round trigger price to tick size
            multiplier = trigger_price / tick_size
            rounded_trigger = multiplier.quantize(Decimal('1'), rounding='ROUND_HALF_UP') * tick_size

            # Use trigger as limit if not specified
            if limit_price is None:
                limit_price = trigger_price
            multiplier = limit_price / tick_size
            rounded_limit = multiplier.quantize(Decimal('1'), rounding='ROUND_HALF_UP') * tick_size
            
            logger.info(
                f"Placing STOP LIMIT BUY order: "
                f"{size} {symbol} triggers @ ${rounded_trigger:.2f}, "
                f"limit @ ${rounded_limit:.2f}"
            )
            # Create stop buy order type (triggers when price rises)
            # Using "sl" (stop loss) for buy orders that trigger when price goes UP        
            order_type = {
                "trigger": {
                    "triggerPx": float(rounded_trigger),
                    "isMarket": True,
                    "tpsl": "sl"  # Stop loss type (for buy orders, triggers when price rises above)                    "tpsl": "sl"
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
            
            # logger.info(f"RAW STOP BUY RESPONSE: {result}")
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
                        filled_size=Decimal("0"),
                        average_price=Decimal(str(rounded_limit))
                    )
                elif statuses and "error" in statuses[0]:
                    error_msg = statuses[0]["error"]
                    return OrderResult(success=False, error_message=error_msg)
                else:
                    return OrderResult(success=False, error_message=f"Unexpected response: {statuses}")
            else:
                error_msg = result.get("response", "Unknown error")
                return OrderResult(success=False, error_message=f"Stop buy order failed: {error_msg}")

        except Exception as e:
            logger.error(f"Failed to place stop buy order: {e}", exc_info=True)
            return OrderResult(success=False, error_message=str(e))
    
    def place_limit_order(
        self,
        symbol: str,
        is_buy: bool,
        price: Decimal,
        size: Decimal,
        reduce_only: bool = False,
        post_only: bool = True
    ) -> OrderResult:
        """
        Place a limit order.
        
        Args:
            symbol: Trading symbol (e.g., "ETH")
            is_buy: True for buy, False for sell
            price: Limit price
            size: Order size in base currency
            reduce_only: If True, order can only reduce position
            post_only: If True, order will only make (not take)
            
        Returns:
            OrderResult with order details
        """
        try:
            # Ensure price and size are Decimals
            price = Decimal(str(price))
            size = Decimal(str(size))

            # Get market info for proper decimal formatting
            market_info = self.get_market_info(symbol)
            sz_decimals = int(market_info.get("szDecimals", 4))

            # Get tick size from market info
            tick_decimals = int(market_info.get("szDecimals", 4))
            tick_size = Decimal(10) ** Decimal(-tick_decimals)

            # Round price to the nearest tick size using Decimal arithmetic
            rounded_price = (price / tick_size).quantize(Decimal('1'), rounding='ROUND_HALF_UP') * tick_size

            # Round size to appropriate decimals using Decimal
            rounded_size = size.quantize(Decimal(10) ** Decimal(-sz_decimals), rounding='ROUND_HALF_UP')
            
            logger.info(
                f"Placing {'BUY' if is_buy else 'SELL'} limit order: "
                f"{rounded_size} {symbol} @ ${rounded_price:.2f}"
            )
            
            # Create order request
            order = {
                "a": 1,  # Asset ID (1 for perp)
                "b": is_buy,
                "p": str(rounded_price),
                "s": str(rounded_size),
                "r": reduce_only,
                "t": {"limit": {"tif": "Gtc"}},  # Good till cancelled
                "c": None  # No client order ID for now
            }

            if post_only:
                order["t"]["limit"]["tif"] = "Alo"  # Add liquidity only

            # Place the order with rounded price (convert to float for SDK)
            result = self.exchange.order(symbol, is_buy, float(rounded_size), float(rounded_price),
                                        {"limit": {"tif": "Gtc"}}, reduce_only=reduce_only)
            
            # logger.info(f"RAW LIMIT ORDER RESPONSE: {result}")
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
                        filled_size=Decimal("0"),
                        average_price=Decimal(str(price))
                    )
                elif statuses and "filled" in statuses[0]:
                    filled = statuses[0]["filled"]
                    return OrderResult(
                        success=True,
                        order_id=str(filled.get("oid")),
                        filled_size=Decimal(str(filled.get("totalSz", 0))),
                        average_price=Decimal(str(filled.get("avgPx", 0)))
                    )
                elif statuses and "error" in statuses[0]:
                    return OrderResult(success=False, error_message=statuses[0]["error"])
            
            return OrderResult(success=False, error_message=f"Unexpected response: {result}")
            
        except Exception as e:
            logger.error(f"Failed to place limit order: {e}", exc_info=True)
            return OrderResult(success=False, error_message=str(e))
    
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
            
            # logger.info(f"RAW CANCEL . ORDER RESPONSE for {order_id}: {result}")
            
            if result.get("status") == "ok":
                logger.info(f"Cancelled order {order_id} for {symbol}")
                return True
            else:
                logger.warning(f"Failed to cancel order: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    def cancel_all_orders(self, symbol: str) -> int:
        """
        Cancel all open orders for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Number of orders cancelled
        """
        try:
            # Get all open orders for this symbol
            open_orders = self.get_open_orders(symbol)
            if not open_orders:
                return 0

            cancelled_count = 0
            for order in open_orders:
                order_id = order.get("oid")
                if order_id and self.cancel_order(symbol, str(order_id)):
                    cancelled_count += 1

            logger.info(f"Cancelled {cancelled_count} orders for {symbol}")
            return cancelled_count

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

    def get_order_history(self, symbol: Optional[str] = None, limit: int = 100) -> list:
        """
        Get order fill history from Hyperliquid.

        Args:
            symbol: Optional symbol to filter by
            limit: Maximum number of fills to retrieve

        Returns:
            List of filled orders
        """
        try:
            user_address = self.get_user_address()
            fills = self.info.user_fills(user_address)

            if symbol:
                fills = [f for f in fills if f.get("coin") == symbol]

            # Limit results
            fills = fills[:limit] if len(fills) > limit else fills

            return fills

        except Exception as e:
            logger.error(f"Failed to get order history: {e}")
            return []
