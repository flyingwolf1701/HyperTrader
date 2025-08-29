"""
CCXT Exchange Client for Hyperliquid
"""
import ccxt
from decimal import Decimal
from typing import Dict, List, Optional
from loguru import logger
from .ccxt_types import Market, Balance, Position, Order, OrderResult

from src.utils import settings


class HyperliquidExchangeClient:
    """CCXT client for interacting with Hyperliquid exchange"""
    
    def __init__(self, testnet: bool = True):
        """
        Initialize Hyperliquid exchange client.
        
        Args:
            testnet: Whether to use testnet (True) or mainnet (False)
        """
        self.testnet = testnet
        self.exchange: Optional[ccxt.Exchange] = None
        self.markets: Dict[str, Market] = {}
        self._initialize_exchange()
        
    def _initialize_exchange(self):
        """Initialize CCXT exchange connection"""
        try:
            # Get credentials from settings
            wallet_address = settings.hyperliquid_wallet_key
            private_key = settings.HYPERLIQUID_TESTNET_PRIVATE_KEY
            
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
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            raw_markets = self.exchange.load_markets()
            self.markets = {}
            for symbol, market_data in raw_markets.items():
                self.markets[symbol] = Market.from_ccxt_market(market_data)
            logger.info(f"Loaded {len(self.markets)} markets")
        except Exception as e:
            logger.error(f"Failed to load markets: {e}")
            raise
    
    def get_market(self, symbol: str) -> Optional[Market]:
        """
        Get market information for a specific symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., "ETH/USDC:USDC")
            
        Returns:
            Market object or None if not found
        """
        return self.markets.get(symbol)
    
    def get_balance(self, currency: str = "USDC") -> Balance:
        """
        Fetch account balance for a specific currency.
        
        Args:
            currency: Currency to fetch balance for (default: USDC)
            
        Returns:
            Balance object with free, used, and total amounts
        """
        try:
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            balance = self.exchange.fetch_balance()
            
            if currency in balance:
                return Balance.from_ccxt_balance(currency, balance[currency])
            else:
                return Balance.empty(currency)
                
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            raise
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Fetch position information for a specific symbol.
        
        Args:
            symbol: Trading pair (e.g., "ETH/USDC:USDC")
            
        Returns:
            Position object or None if no position
        """
        try:
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            positions = self.exchange.fetch_positions([symbol])
            
            # Filter for active positions (contracts != 0)
            active_positions = [pos for pos in positions if float(pos.get("contracts", 0)) != 0]
            
            if active_positions:
                return Position.from_ccxt_position(active_positions[0])
            
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
                market = self.markets[symbol]
                if market.info and "midPx" in market.info:
                    return Decimal(str(market.info["midPx"]))
            
            # Fallback to ticker
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            ticker = self.exchange.fetch_ticker(symbol)
            return Decimal(str(ticker["last"]))
            
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            raise
    
    def set_leverage(self, symbol: str, leverage: Optional[int]) -> bool:
        """
        Set leverage for a symbol.
        
        Args:
            symbol: Trading pair
            leverage: Leverage multiplier
            
        Returns:
            True if successful
        """
        try:
            if leverage is None:
                return False
            if self.exchange:
                self.exchange.set_leverage(leverage, symbol)
            else:
                return False
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
    ) -> Order:
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
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            formatted_amount = float(self.exchange.amount_to_precision(symbol, amount_float))
            
            # Get current price for the order
            current_price = float(self.get_current_price(symbol))
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            formatted_price = float(self.exchange.price_to_precision(symbol, current_price))
            
            # Prepare parameters
            params = {"reduceOnly": reduce_only}
            
            logger.info(
                f"Placing market {side} order: {formatted_amount} {symbol} "
                f"at ~${formatted_price} (reduce_only={reduce_only})"
            )
            
            # Place the order
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            order = self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=formatted_amount,
                price=formatted_price,
                params=params
            )
            
            logger.info(f"Order placed successfully: {order['id']}")
            
            return Order.from_ccxt_order(order)
            
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            raise
    
    
    def close_position(self, symbol: str) -> Optional[Order]:
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
            close_side = "sell" if position.side == "long" else "buy"
            amount = abs(position.contracts)
            
            logger.info(f"Closing {position.side} position: {amount} {symbol}")
            
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
    
    # ================================================================================
    # CORRECTED METHODS: USD Buy, ETH Sell Pattern for HyperTrader Strategy
    # ================================================================================
    
    async def buy_long_usd(self, symbol: str, usd_amount: Decimal, leverage: int = 25) -> OrderResult:
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
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=float(eth_amount),  # ETH amount to buy
                price=float(current_price),  # Pass price directly for Hyperliquid
                params={'reduceOnly': False}  # CRITICAL: This opens new long position instead of reducing short
            )
            
            logger.success("✅ Long position opened:")
            logger.success(f"   ${usd_amount} → {eth_amount:.6f} ETH")
            
            return OrderResult(
                id=order.get("id", ""),
                type="buy_long_usd",
                usd_amount=usd_amount,
                eth_amount=eth_amount,
                price=current_price,
                leverage=leverage,
                margin_used=margin_needed,
                status=order.get("status"),
                info=order.get("info", {})
            )
            
        except Exception as e:
            logger.error(f"Failed to buy long with USD: {e}")
            raise
    
    async def open_short_usd(self, symbol: str, usd_amount: Decimal, leverage: int = 25) -> OrderResult:
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
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='sell',
                amount=float(eth_amount),  # ETH amount to short
                price=float(current_price),  # Pass price directly for Hyperliquid
                params={'reduceOnly': False}  # CRITICAL: This opens new short position instead of reducing long
            )
            
            logger.success("✅ Short position opened:")
            logger.success(f"   ${usd_amount} → {eth_amount:.6f} ETH short")
            
            return OrderResult(
                id=order.get("id", ""),
                type="open_short_usd",
                usd_amount=usd_amount,
                eth_amount=eth_amount,
                price=current_price,
                leverage=leverage,
                margin_used=margin_needed,
                status=order.get("status"),
                info=order.get("info", {})
            )
            
        except Exception as e:
            logger.error(f"Failed to open short with USD: {e}")
            raise
    
    async def sell_long_eth(self, symbol: str, eth_amount: Decimal, reduce_only: bool = True) -> OrderResult:
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
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='sell',
                amount=float(eth_amount),  # Specific ETH amount to sell
                price=float(current_price),  # Pass price directly for Hyperliquid
                params=params
            )
            
            logger.success("✅ Long position reduced:")
            logger.success(f"   {eth_amount:.6f} ETH → ${usd_value:.2f}")
            
            return OrderResult(
                id=order.get("id", ""),
                type="sell_long_eth",
                eth_amount=eth_amount,
                usd_received=usd_value,
                price=current_price,
                reduce_only=reduce_only,
                status=order.get("status"),
                info=order.get("info", {})
            )
            
        except Exception as e:
            logger.error(f"Failed to sell long with ETH: {e}")
            raise
    
    async def close_short_eth(self, symbol: str, eth_amount: Decimal) -> OrderResult:
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
            if not self.exchange:
                raise ValueError("Exchange not initialized")
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=float(eth_amount),  # Specific ETH amount to buy back
                price=float(current_price),  # Pass price directly for Hyperliquid
                params={'reduceOnly': True}
            )
            
            logger.success("✅ Short position closed:")
            logger.success(f"   {eth_amount:.6f} ETH closed for ${usd_cost:.2f}")
            
            return OrderResult(
                id=order.get("id", ""),
                type="close_short_eth",
                eth_amount=eth_amount,
                usd_cost=usd_cost,
                price=current_price,
                status=order.get("status"),
                info=order.get("info", {})
            )
            
        except Exception as e:
            logger.error(f"Failed to close short with ETH: {e}")
            raise
    

