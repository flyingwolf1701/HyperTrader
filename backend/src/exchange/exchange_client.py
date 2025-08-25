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
            
            return {
                "id": order["id"],
                "symbol": order["symbol"],
                "side": order["side"],
                "amount": Decimal(str(order["amount"])),
                "price": Decimal(str(order.get("price", 0))),
                "status": order["status"],
                "info": order.get("info", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            raise
    
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
            raise