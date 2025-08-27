"""
CCXT Exchange Client for Hyperliquid
Stage 3: Exchange Integration
"""
import ccxt
from decimal import Decimal
from typing import Dict, List, Optional, Any
from loguru import logger

try:
    from ..utils import settings
except ImportError:
    from utils.config import settings


class HyperliquidExchangeClient:
    """CCXT client for interacting with Hyperliquid exchange"""
    
    def __init__(self, testnet: bool = True):
        """
        Initialize Hyperliquid exchange client.
        
        Args:
            testnet: Whether to use testnet (True) or mainnet (False)
        """
        self.testnet = testnet
        self.exchange = None
        self.markets = {}
        self._initialize_exchange()
        
    def _initialize_exchange(self):
        """Initialize CCXT exchange connection"""
        try:
            # Get credentials from settings
            wallet_address = settings.hyperliquid_wallet_key
            private_key = settings.hyperliquid_private_key
            
            if not wallet_address or not private_key:
                raise ValueError("Wallet address and private key are required")
            
            # Initialize exchange
            self.exchange = ccxt.hyperliquid({
                "walletAddress": wallet_address,
                "privateKey": private_key,
                "enableRateLimit": True,
            })
            
            # Set testnet if needed
            if self.testnet:
                self.exchange.set_sandbox_mode(True)
            
            # Load markets
            self._load_markets()
            
            logger.info(f"Initialized Hyperliquid {'testnet' if self.testnet else 'mainnet'} exchange client")
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise
    
    def _load_markets(self):
        """Load market data from the exchange"""
        try:
            self.markets = self.exchange.load_markets()
            logger.info(f"Loaded {len(self.markets)} markets")
        except Exception as e:
            logger.error(f"Failed to load markets: {e}")
            raise
    
    def get_balance(self, currency: str = "USDC") -> Dict[str, Decimal]:
        """
        Fetch account balance for a specific currency.
        
        Args:
            currency: Currency to fetch balance for (default: USDC)
            
        Returns:
            Dictionary with 'free', 'used', and 'total' balances as Decimal
        """
        try:
            balance = self.exchange.fetch_balance()
            
            if currency in balance:
                return {
                    "free": Decimal(str(balance[currency]["free"])),
                    "used": Decimal(str(balance[currency]["used"])),
                    "total": Decimal(str(balance[currency]["total"]))
                }
            else:
                return {
                    "free": Decimal("0"),
                    "used": Decimal("0"),
                    "total": Decimal("0")
                }
                
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            raise
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch position information for a specific symbol.
        
        Args:
            symbol: Trading pair (e.g., "ETH/USDC:USDC")
            
        Returns:
            Position dictionary or None if no position
        """
        try:
            positions = self.exchange.fetch_positions([symbol])
            
            # Filter for active positions (contracts != 0)
            active_positions = [pos for pos in positions if float(pos.get("contracts", 0)) != 0]
            
            if active_positions:
                pos = active_positions[0]
                return {
                    "symbol": pos["symbol"],
                    "side": pos["side"],  # "long" or "short"
                    "contracts": Decimal(str(pos.get("contracts", 0))),
                    "contractSize": Decimal(str(pos.get("contractSize", 1))),
                    "percentage": Decimal(str(pos.get("percentage", 0) or 0)),
                    "unrealizedPnl": Decimal(str(pos.get("unrealizedPnl", 0) or 0)),
                    "markPrice": Decimal(str(pos.get("markPrice", 0) or 0)),
                    "entryPrice": Decimal(str(pos.get("info", {}).get("entryPx", 0) or 0))
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch position for {symbol}: {e}")
            raise
    
    def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current market price for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "ETH/USDC:USDC")
            
        Returns:
            Current market price as Decimal
        """
        try:
            if symbol in self.markets:
                mid_price = self.markets[symbol]["info"].get("midPx")
                if mid_price:
                    return Decimal(str(mid_price))
            
            # Fallback to ticker
            ticker = self.exchange.fetch_ticker(symbol)
            return Decimal(str(ticker["last"]))
            
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            raise
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a symbol.
        
        Args:
            symbol: Trading pair
            leverage: Leverage multiplier
            
        Returns:
            True if successful
        """
        try:
            self.exchange.set_leverage(leverage, symbol)
            logger.info(f"Set leverage to {leverage}x for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False
    
    def place_market_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Place a market order.
        
        Args:
            symbol: Trading pair (e.g., "ETH/USDC:USDC")
            side: "buy" or "sell"
            amount: Order size in contracts as Decimal
            reduce_only: If True, order will only reduce position
            
        Returns:
            Order execution details
        """
        try:
            # Convert Decimal to float for CCXT
            amount_float = float(amount)
            
            # Format amount to exchange precision
            formatted_amount = float(self.exchange.amount_to_precision(symbol, amount_float))
            
            # Get current price for the order
            current_price = float(self.get_current_price(symbol))
            formatted_price = float(self.exchange.price_to_precision(symbol, current_price))
            
            # Prepare parameters
            params = {"reduceOnly": reduce_only}
            
            logger.info(
                f"Placing market {side} order: {formatted_amount} {symbol} "
                f"at ~${formatted_price} (reduce_only={reduce_only})"
            )
            
            # Place the order
            order = self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=formatted_amount,
                price=formatted_price,
                params=params
            )
            
            logger.info(f"Order placed successfully: {order['id']}")
            
            # Safely convert values, handling None and missing fields
            return {
                "id": order.get("id"),
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "amount": Decimal(str(order.get("amount", 0))) if order.get("amount") is not None else Decimal("0"),
                "price": Decimal(str(order.get("price", 0))) if order.get("price") is not None else Decimal("0"),
                "status": order.get("status"),
                "info": order.get("info", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            raise
    
    def reduce_position(self, symbol: str, amount: Decimal, side: str) -> Optional[Dict[str, Any]]:
        """
        Reduce an existing position by a specific amount
        
        Args:
            symbol: Trading pair
            amount: Amount to reduce (in base currency)
            side: "buy" to reduce short, "sell" to reduce long
        """
        try:
            logger.info(f"Reducing position for {symbol} by {amount:.6f}")
            
            # Place reduce-only order
            order = self.place_market_order(
                symbol=symbol,
                side=side,
                amount=float(amount),
                reduce_only=True
            )
            
            if order:
                logger.success(f"Position reduced successfully")
            
            return order
            
        except Exception as e:
            logger.error(f"Error reducing position: {e}")
            return None
    
    def add_to_position(self, symbol: str, position_size_usd: Decimal, side: str) -> Optional[Dict[str, Any]]:
        """
        Add to an existing position
        
        Args:
            symbol: Trading pair
            position_size_usd: Size to add in USD
            side: "buy" for long, "sell" for short
        """
        try:
            current_price = self.get_current_price(symbol)
            if not current_price:
                logger.error("Could not get current price")
                return None
            
            amount = position_size_usd / current_price
            logger.info(f"Adding ${position_size_usd} to {side} position ({amount:.6f} {symbol.split('/')[0]})")
            
            # Place order to add to position
            order = self.place_market_order(
                symbol=symbol,
                side=side,
                amount=float(amount),
                reduce_only=False
            )
            
            if order:
                logger.success(f"Added to position successfully")
            
            return order
            
        except Exception as e:
            logger.error(f"Error adding to position: {e}")
            return None
    
    def close_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Close an existing position.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Order details if position was closed, None if no position
        """
        try:
            position = self.get_position(symbol)
            
            if not position:
                logger.info(f"No position to close for {symbol}")
                return None
            
            # Determine close side (opposite of position side)
            close_side = "sell" if position["side"] == "long" else "buy"
            amount = abs(position["contracts"])
            
            logger.info(f"Closing {position['side']} position: {amount} {symbol}")
            
            # Place reduce-only order to close
            return self.place_market_order(
                symbol=symbol,
                side=close_side,
                amount=amount,
                reduce_only=True
            )
            
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            raise
    
    def open_long(
        self,
        symbol: str,
        position_size_usd: Decimal,
        leverage: int = None
    ) -> Dict[str, Any]:
        """
        Open a long position.
        
        Args:
            symbol: Trading pair (e.g., "ETH/USDC:USDC")
            position_size_usd: Position size in USD
            leverage: Optional leverage to set
            
        Returns:
            Order execution details
        """
        try:
            # Set leverage if specified
            if leverage:
                self.set_leverage(symbol, leverage)
            
            # Get current price
            current_price = self.get_current_price(symbol)
            
            # Calculate amount in contracts
            amount = position_size_usd / current_price
            
            logger.info(f"Opening LONG position: ${position_size_usd} ({amount:.6f} {symbol.split('/')[0]})")
            
            # Place buy order
            return self.place_market_order(
                symbol=symbol,
                side="buy",
                amount=amount,
                reduce_only=False
            )
            
        except Exception as e:
            logger.error(f"Failed to open long position: {e}")
            raise
    
    def open_short(
        self,
        symbol: str,
        position_size_usd: Decimal,
        leverage: int = None
    ) -> Dict[str, Any]:
        """
        Open a short position.
        
        Args:
            symbol: Trading pair (e.g., "ETH/USDC:USDC")
            position_size_usd: Position size in USD
            leverage: Optional leverage to set
            
        Returns:
            Order execution details
        """
        try:
            # Set leverage if specified
            if leverage:
                self.set_leverage(symbol, leverage)
            
            # Get current price
            current_price = self.get_current_price(symbol)
            
            # Calculate amount in contracts
            amount = position_size_usd / current_price
            
            logger.info(f"Opening SHORT position: ${position_size_usd} ({amount:.6f} {symbol.split('/')[0]})")
            
            # Place sell order
            return self.place_market_order(
                symbol=symbol,
                side="sell",
                amount=amount,
                reduce_only=False
            )
            
        except Exception as e:
            logger.error(f"Failed to open short position: {e}")
            raise    # ================================================================================
    # CORRECTED METHODS: USD Buy, ETH Sell Pattern for HyperTrader Strategy
    # ================================================================================
    
    async def buy_long_usd(self, symbol: str, usd_amount: Decimal, leverage: int = 25) -> Dict[str, Any]:
        """
        CORRECTED: Buy long position using USD amount
        Perfect for: Initial entries, recovery purchases, position scaling
        """
        try:
            if leverage:
                self.set_leverage(symbol, leverage)
            
            current_price = self.get_current_price(symbol)
            margin_needed = usd_amount / Decimal(leverage)
            eth_amount = usd_amount / current_price
            
            logger.info(f"🟢 BUYING LONG (USD-based):")
            logger.info(f"  USD Amount: ${usd_amount}")
            logger.info(f"  Current Price: ${current_price}")
            logger.info(f"  ETH Amount: {eth_amount:.6f} ETH")
            logger.info(f"  Leverage: {leverage}x")
            logger.info(f"  Margin Needed: ${margin_needed}")
            
            # Use create_order for market orders (Hyperliquid requires price)
            # CRITICAL: Use reduceOnly: False to ensure we open a NEW long position
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=float(eth_amount),  # ETH amount to buy
                price=float(current_price),  # Pass price directly for Hyperliquid
                params={'reduceOnly': False}  # CRITICAL: This opens new long position instead of reducing short
            )
            
            logger.success(f"✅ Long position opened:")
            logger.success(f"   ${usd_amount} → {eth_amount:.6f} ETH")
            
            return {
                "id": order.get("id"),
                "type": "buy_long_usd",
                "usd_amount": usd_amount,
                "eth_amount": eth_amount,
                "price": current_price,
                "leverage": leverage,
                "margin_used": margin_needed,
                "status": order.get("status"),
                "info": order.get("info", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to buy long with USD: {e}")
            raise
    
    async def open_short_usd(self, symbol: str, usd_amount: Decimal, leverage: int = 25) -> Dict[str, Any]:
        """
        CORRECTED: Open short position using USD amount
        Perfect for: Consistent short position sizing during retracement
        """
        try:
            if leverage:
                self.set_leverage(symbol, leverage)
            
            current_price = self.get_current_price(symbol)
            margin_needed = usd_amount / Decimal(leverage)
            eth_amount = usd_amount / current_price
            
            logger.info(f"🔴 OPENING SHORT (USD-based):")
            logger.info(f"  USD Amount: ${usd_amount}")
            logger.info(f"  Current Price: ${current_price}")
            logger.info(f"  ETH Amount: {eth_amount:.6f} ETH")
            logger.info(f"  Leverage: {leverage}x")
            logger.info(f"  Margin Needed: ${margin_needed}")
            
            # Use create_order for market orders (Hyperliquid requires price)
            # CRITICAL: Use reduceOnly: False to ensure we open a NEW short position
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='sell',
                amount=float(eth_amount),  # ETH amount to short
                price=float(current_price),  # Pass price directly for Hyperliquid
                params={'reduceOnly': False}  # CRITICAL: This opens new short position instead of reducing long
            )
            
            logger.success(f"✅ Short position opened:")
            logger.success(f"   ${usd_amount} → {eth_amount:.6f} ETH short")
            
            return {
                "id": order.get("id"),
                "type": "open_short_usd", 
                "usd_amount": usd_amount,
                "eth_amount": eth_amount,
                "price": current_price,
                "leverage": leverage,
                "margin_used": margin_needed,
                "status": order.get("status"),
                "info": order.get("info", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to open short with USD: {e}")
            raise
    
    async def sell_long_eth(self, symbol: str, eth_amount: Decimal, reduce_only: bool = True) -> Dict[str, Any]:
        """
        CORRECTED: Sell long position using ETH amount
        Perfect for: RETRACEMENT scaling - sell same ETH amount regardless of price
        """
        try:
            current_price = self.get_current_price(symbol)
            usd_value = eth_amount * current_price
            
            logger.info(f"🟡 SELLING LONG (ETH-based):")
            logger.info(f"  ETH Amount: {eth_amount:.6f} ETH")
            logger.info(f"  Current Price: ${current_price}")  
            logger.info(f"  USD Value: ${usd_value:.2f}")
            logger.info(f"  Reduce Only: {reduce_only}")
            
            # Use create_order for market orders (Hyperliquid requires price)
            params = {'reduceOnly': reduce_only} if reduce_only else {}
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='sell',
                amount=float(eth_amount),  # Specific ETH amount to sell
                price=float(current_price),  # Pass price directly for Hyperliquid
                params=params
            )
            
            logger.success(f"✅ Long position reduced:")
            logger.success(f"   {eth_amount:.6f} ETH → ${usd_value:.2f}")
            
            return {
                "id": order.get("id"),
                "type": "sell_long_eth",
                "eth_amount": eth_amount,
                "usd_received": usd_value,
                "price": current_price,
                "reduce_only": reduce_only,
                "status": order.get("status"),
                "info": order.get("info", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to sell long with ETH: {e}")
            raise
    
    async def close_short_eth(self, symbol: str, eth_amount: Decimal) -> Dict[str, Any]:
        """
        CORRECTED: Close short position using ETH amount
        Perfect for: RECOVERY phase - close whatever ETH amount the hedge fragment represents
        """
        try:
            current_price = self.get_current_price(symbol)
            usd_cost = eth_amount * current_price
            
            logger.info(f"🟢 CLOSING SHORT (ETH-based):")
            logger.info(f"  ETH Amount: {eth_amount:.6f} ETH")
            logger.info(f"  Current Price: ${current_price}")
            logger.info(f"  USD Cost: ${usd_cost:.2f}")
            
            # Use create_order for market orders (Hyperliquid requires price)
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=float(eth_amount),  # Specific ETH amount to buy back
                price=float(current_price),  # Pass price directly for Hyperliquid
                params={'reduceOnly': True}
            )
            
            logger.success(f"✅ Short position closed:")
            logger.success(f"   {eth_amount:.6f} ETH closed for ${usd_cost:.2f}")
            
            return {
                "id": order.get("id"),
                "type": "close_short_eth",
                "eth_amount": eth_amount,
                "usd_cost": usd_cost,
                "price": current_price,
                "status": order.get("status"),
                "info": order.get("info", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to close short with ETH: {e}")
            raise
    
    def close_all_positions(self, symbol: str) -> List[Dict[str, Any]]:
        """CORRECTED: Close all positions for a symbol"""
        try:
            position = self.get_position(symbol)
            if not position:
                logger.info(f"No positions to close for {symbol}")
                return []
            
            orders = []
            
            # Get position details
            side = position.get("side")
            contracts = abs(position.get("contracts", 0))
            
            if contracts == 0:
                logger.info(f"No active position to close for {symbol}")
                return []
            
            logger.info(f"Closing {side} position: {contracts:.6f} contracts")
            
            if side == "long":
                # Close long by selling
                order = self.place_market_order(
                    symbol=symbol,
                    side="sell",
                    amount=Decimal(str(contracts)),
                    reduce_only=True
                )
                if order:
                    orders.append(order)
                    logger.success(f"✅ Closed long position: {contracts:.6f} ETH")
                    
            elif side == "short":
                # Close short by buying back
                order = self.place_market_order(
                    symbol=symbol,
                    side="buy",
                    amount=Decimal(str(contracts)),
                    reduce_only=True
                )
                if order:
                    orders.append(order)
                    logger.success(f"✅ Closed short position: {contracts:.6f} ETH")
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to close positions: {e}")
            raise

