import ccxt.pro as ccxt
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    """Result of an order execution"""
    success: bool
    order_id: Optional[str] = None
    filled_amount: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    cost: Optional[Decimal] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict] = None


@dataclass
class MarketInfo:
    """Market information structure"""
    symbol: str
    base: str
    quote: str
    active: bool
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None


class ExchangeManager:
    """
    Exchange manager class that wraps ccxt library for HyperLiquid integration.
    Handles order placement, market data, and price monitoring.
    """
    
    def __init__(self):
        self.exchange = None
        self.connected = False
        self._markets = {}
        self._last_prices = {}
        
    async def initialize(self):
        """Initialize the exchange connection"""
        try:
            # Initialize HyperLiquid exchange with ccxt
            self.exchange = ccxt.hyperliquid({
                'apiKey': settings.HYPERLIQUID_API_KEY,
                'secret': settings.HYPERLIQUID_SECRET_KEY,
                'sandbox': settings.HYPERLIQUID_TESTNET,
                'rateLimit': True,  # Enable rate limiting
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',  # Use perpetual futures by default
                }
            })
            
            # Load markets
            await self.load_markets()
            
            self.connected = True
            logger.info("ExchangeManager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise
    
    async def close(self):
        """Close exchange connections"""
        if self.exchange:
            await self.exchange.close()
            self.connected = False
            logger.info("Exchange connection closed")
    
    async def load_markets(self) -> Dict[str, MarketInfo]:
        """Load available markets from the exchange"""
        try:
            markets_data = await self.exchange.load_markets()
            self._markets = {}
            
            for symbol, market_data in markets_data.items():
                market_info = MarketInfo(
                    symbol=symbol,
                    base=market_data['base'],
                    quote=market_data['quote'],
                    active=market_data.get('active', True),
                    min_amount=Decimal(str(market_data['limits']['amount']['min'])) if market_data['limits']['amount']['min'] else None,
                    max_amount=Decimal(str(market_data['limits']['amount']['max'])) if market_data['limits']['amount']['max'] else None,
                    min_price=Decimal(str(market_data['limits']['price']['min'])) if market_data['limits']['price']['min'] else None,
                    max_price=Decimal(str(market_data['limits']['price']['max'])) if market_data['limits']['price']['max'] else None,
                )
                self._markets[symbol] = market_info
            
            logger.info(f"Loaded {len(self._markets)} markets")
            return self._markets
            
        except Exception as e:
            logger.error(f"Failed to load markets: {e}")
            raise
    
    async def fetch_markets(self) -> List[MarketInfo]:
        """Fetch all available markets"""
        if not self._markets:
            await self.load_markets()
        return list(self._markets.values())
    
    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current price for a symbol"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            price = Decimal(str(ticker['last']))
            self._last_prices[symbol] = price
            return price
            
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None
    
    async def place_order(
        self,
        symbol: str,
        order_type: str,  # 'market', 'limit'
        side: str,        # 'buy', 'sell'
        amount: Decimal,
        price: Optional[Decimal] = None,
        reduce_only: bool = False,
        timeout: int = 30
    ) -> OrderResult:
        """
        Place an order on the exchange with robust error handling
        
        Args:
            symbol: Trading pair symbol
            order_type: 'market' or 'limit'
            side: 'buy' or 'sell'
            amount: Order size
            price: Limit price (required for limit orders)
            reduce_only: Whether this is a position reduction order
            timeout: Timeout in seconds
        """
        max_retries = 3
        retry_delay = 1  # Start with 1 second delay
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Placing {side} {order_type} order: {amount} {symbol} (attempt {attempt + 1})")
                
                # Build order parameters
                params = {}
                if reduce_only:
                    params['reduce_only'] = True
                
                # Place the order
                if order_type.lower() == 'market':
                    order_response = await self.exchange.create_market_order(
                        symbol=symbol,
                        side=side,
                        amount=float(amount),
                        params=params
                    )
                elif order_type.lower() == 'limit':
                    if price is None:
                        raise ValueError("Price is required for limit orders")
                    order_response = await self.exchange.create_limit_order(
                        symbol=symbol,
                        side=side,
                        amount=float(amount),
                        price=float(price),
                        params=params
                    )
                else:
                    raise ValueError(f"Unsupported order type: {order_type}")
                
                # Parse successful response
                return OrderResult(
                    success=True,
                    order_id=order_response.get('id'),
                    filled_amount=Decimal(str(order_response.get('filled', 0))),
                    average_price=Decimal(str(order_response.get('average', 0))) if order_response.get('average') else None,
                    cost=Decimal(str(order_response.get('cost', 0))) if order_response.get('cost') else None,
                    raw_response=order_response
                )
                
            except Exception as e:
                logger.warning(f"Order attempt {attempt + 1} failed for {symbol}: {e}")
                
                if attempt < max_retries - 1:
                    # Wait before retrying with exponential backoff
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    # Final attempt failed
                    logger.error(f"All order attempts failed for {symbol}: {e}")
                    return OrderResult(
                        success=False,
                        error_message=str(e)
                    )
    
    async def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for a symbol"""
        try:
            positions = await self.exchange.fetch_positions([symbol])
            if positions:
                return positions[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None
    
    async def get_balance(self) -> Optional[Dict]:
        """Get account balance"""
        try:
            balance = await self.exchange.fetch_balance()
            return balance
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None
    
    def is_market_available(self, symbol: str) -> bool:
        """Check if a market is available for trading"""
        market = self._markets.get(symbol)
        return market is not None and market.active
    
    def get_market_info(self, symbol: str) -> Optional[MarketInfo]:
        """Get market information for a symbol"""
        return self._markets.get(symbol)


# Global exchange manager instance
exchange_manager = ExchangeManager()