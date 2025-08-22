import asyncio
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import ccxt.async_support as ccxt
from loguru import logger

from app.core.config import settings

class MarketInfo(BaseModel):
    symbol: str
    base: str
    quote: str
    active: bool
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None

class OrderResult(BaseModel):
    success: bool
    order_id: Optional[str] = None
    error_message: Optional[str] = None
    average_price: Optional[Decimal] = None
    cost: Optional[Decimal] = None

class Position(BaseModel):
    symbol: str
    side: str  # 'long' or 'short'
    size: Decimal  # Position size in base currency
    notional: Decimal  # Position value in quote currency
    entry_price: Decimal  # Average entry price
    mark_price: Decimal  # Current mark price
    pnl: Decimal  # Unrealized PnL
    percentage: Optional[Decimal] = None  # PnL percentage
    contracts: Optional[Decimal] = None  # Number of contracts (for futures)
    
class Trade(BaseModel):
    id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: Decimal  # Trade amount in base currency
    price: Decimal  # Trade price
    cost: Decimal  # Total cost in quote currency
    fee: Optional[Decimal] = None  # Trading fee
    timestamp: Optional[int] = None  # Trade timestamp
    datetime: Optional[str] = None  # Human-readable datetime

class Order(BaseModel):
    id: str
    symbol: str
    type: str  # 'market', 'limit', etc.
    side: str  # 'buy' or 'sell'
    amount: Decimal  # Order amount
    price: Optional[Decimal] = None  # Order price (None for market orders)
    filled: Decimal  # Amount filled
    remaining: Decimal  # Amount remaining
    status: str  # 'open', 'closed', 'canceled', etc.
    timestamp: Optional[int] = None
    datetime: Optional[str] = None

class ExchangeManager:
    def __init__(self):
        self.exchange = None
        self.markets: Dict[str, MarketInfo] = {}

    async def initialize(self):
        """Initializes the ccxt exchange instance with credentials."""
        try:
            self.exchange = ccxt.hyperliquid({
                'walletAddress': settings.HYPERLIQUID_WALLET_KEY,
                'privateKey': settings.HYPERLIQUID_PRIVATE_KEY,
                'options': {
                    'testnet': settings.HYPERLIQUID_TESTNET,
                },
                'sandbox': settings.HYPERLIQUID_TESTNET
            })
            
            
            await self.fetch_markets()
            logger.info(f"ExchangeManager initialized with {len(self.markets)} markets.")
        except Exception as e:
            logger.error(f"Failed to initialize ExchangeManager: {e}", exc_info=True)
            raise

    async def close(self):
        if self.exchange:
            await self.exchange.close()
            logger.info("Exchange connection closed.")

    async def fetch_markets(self) -> List[MarketInfo]:
        try:
            loaded_markets = await self.exchange.load_markets()
            self.markets = {
                market['symbol']: MarketInfo(
                    symbol=market['symbol'],
                    base=market['base'],
                    quote=market['quote'],
                    active=market.get('active', True),
                    min_amount=market['limits']['amount']['min'],
                    max_amount=market['limits']['amount']['max'],
                    min_price=market['limits']['price']['min'],
                    max_price=market['limits']['price']['max'],
                )
                for market in loaded_markets.values()
            }
            return list(self.markets.values())
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    def is_market_available(self, symbol: str) -> bool:
        return symbol in self.markets and self.markets[symbol].active

    def get_market_info(self, symbol: str) -> Optional[MarketInfo]:
        return self.markets.get(symbol)

    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        try:
            if not self.is_market_available(symbol):
                return None
            ticker = await self.exchange.fetch_ticker(symbol)
            return Decimal(str(ticker['last']))
        except Exception as e:
            logger.error(f"Could not fetch price for {symbol}: {e}")
            return None

    async def place_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[Decimal] = None,
        params: dict = {}
    ) -> OrderResult:
        """
        Places a single order on the exchange without a retry loop.
        This prevents creating multiple positions on transient errors.
        """
        try:
            price_float = float(price) if price is not None else None
            
            logger.info(f"Placing {side} {order_type} order: {amount} {symbol} with reference price ${price_float}")

            order = await self.exchange.create_order(
                symbol, order_type, side, amount, price_float, params
            )
            
            logger.info(f"Successfully placed order for {amount} {symbol}. Processing response...")
            
            # --- FIX: Robustly handle the response from the exchange ---
            # This try-except block prevents the decimal.ConversionSyntax error.
            try:
                avg_price_str = str(order.get("average", "0.0"))
                cost_str = str(order.get("cost", "0.0"))
                avg_price = Decimal(avg_price_str) if avg_price_str else Decimal("0.0")
                cost = Decimal(cost_str) if cost_str else Decimal("0.0")
            except (InvalidOperation, TypeError) as e:
                logger.error(f"Could not parse order response values: {e}. Defaulting to 0.")
                avg_price = Decimal("0.0")
                cost = Decimal("0.0")

            return OrderResult(
                success=True,
                order_id=order.get("id"),
                average_price=avg_price,
                cost=cost,
            )
            # --- END FIX ---

        except Exception as e:
            logger.error(f"Failed to place order: {e}", exc_info=True)
            return OrderResult(success=False, error_message=str(e))

    async def fetch_all_balances(self):
        try:
            # HyperLiquid requires user parameter for account-specific calls
            params = {'user': settings.HYPERLIQUID_WALLET_KEY}
            balance = await self.exchange.fetch_balance(params=params)
            return balance.get('total', {})
        except Exception as e:
            logger.error(f"Could not fetch balances: {e}")
            return {}

    async def fetch_positions(self, symbols: Optional[List[str]] = None) -> List[Position]:
        """
        Fetch all open positions or positions for specific symbols.
        
        Args:
            symbols: Optional list of symbols to filter positions
            
        Returns:
            List of Position objects
        """
        try:
            # HyperLiquid requires user parameter for account-specific calls
            params = {'user': settings.HYPERLIQUID_WALLET_KEY}
            raw_positions = await self.exchange.fetch_positions(symbols, params=params)
            positions = []
            
            for pos in raw_positions:
                # Only include positions with non-zero size
                if pos.get('contracts', 0) == 0 and pos.get('size', 0) == 0:
                    continue
                    
                position = Position(
                    symbol=pos['symbol'],
                    side=pos.get('side', 'unknown'),
                    size=Decimal(str(pos.get('size', 0))),
                    notional=Decimal(str(pos.get('notional', 0))),
                    entry_price=Decimal(str(pos.get('entryPrice', 0))),
                    mark_price=Decimal(str(pos.get('markPrice', 0))),
                    pnl=Decimal(str(pos.get('unrealizedPnl', 0))),
                    percentage=Decimal(str(pos.get('percentage', 0))) if pos.get('percentage') else None,
                    contracts=Decimal(str(pos.get('contracts', 0))) if pos.get('contracts') else None
                )
                positions.append(position)
                
            logger.info(f"Fetched {len(positions)} open positions")
            return positions
            
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}", exc_info=True)
            return []

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Fetch all open orders or open orders for a specific symbol.
        
        Args:
            symbol: Optional symbol to filter orders
            
        Returns:
            List of Order objects
        """
        try:
            # HyperLiquid requires user parameter for account-specific calls
            params = {'user': settings.HYPERLIQUID_WALLET_KEY}
            raw_orders = await self.exchange.fetch_open_orders(symbol, params=params)
            orders = []
            
            for order in raw_orders:
                order_obj = Order(
                    id=order['id'],
                    symbol=order['symbol'],
                    type=order.get('type', 'unknown'),
                    side=order.get('side', 'unknown'),
                    amount=Decimal(str(order.get('amount', 0))),
                    price=Decimal(str(order.get('price', 0))) if order.get('price') else None,
                    filled=Decimal(str(order.get('filled', 0))),
                    remaining=Decimal(str(order.get('remaining', 0))),
                    status=order.get('status', 'unknown'),
                    timestamp=order.get('timestamp'),
                    datetime=order.get('datetime')
                )
                orders.append(order_obj)
                
            logger.info(f"Fetched {len(orders)} open orders")
            return orders
            
        except Exception as e:
            logger.error(f"Failed to fetch open orders: {e}", exc_info=True)
            return []

    async def fetch_my_trades(self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None) -> List[Trade]:
        """
        Fetch recent trades (fills) for the account.
        
        Args:
            symbol: Optional symbol to filter trades
            since: Optional timestamp to fetch trades since
            limit: Optional limit on number of trades to fetch
            
        Returns:
            List of Trade objects
        """
        try:
            # HyperLiquid requires user parameter for account-specific calls  
            params = {'user': settings.HYPERLIQUID_WALLET_KEY}
            raw_trades = await self.exchange.fetch_my_trades(symbol, since, limit, params=params)
            trades = []
            
            for trade in raw_trades:
                trade_obj = Trade(
                    id=trade['id'],
                    symbol=trade['symbol'],
                    side=trade.get('side', 'unknown'),
                    amount=Decimal(str(trade.get('amount', 0))),
                    price=Decimal(str(trade.get('price', 0))),
                    cost=Decimal(str(trade.get('cost', 0))),
                    fee=Decimal(str(trade.get('fee', {}).get('cost', 0))) if trade.get('fee') else None,
                    timestamp=trade.get('timestamp'),
                    datetime=trade.get('datetime')
                )
                trades.append(trade_obj)
                
            logger.info(f"Fetched {len(trades)} trades")
            return trades
            
        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}", exc_info=True)
            return []

    async def get_position_summary(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a summary of all positions with totals and key metrics.
        
        Args:
            symbol: Optional symbol to filter summary
            
        Returns:
            Dictionary with position summary
        """
        try:
            positions = await self.fetch_positions([symbol] if symbol else None)
            
            total_pnl = sum(pos.pnl for pos in positions)
            total_notional = sum(abs(pos.notional) for pos in positions)
            
            long_positions = [pos for pos in positions if pos.side == 'long']
            short_positions = [pos for pos in positions if pos.side == 'short']
            
            summary = {
                'total_positions': len(positions),
                'long_positions': len(long_positions),
                'short_positions': len(short_positions),
                'total_unrealized_pnl': float(total_pnl),
                'total_notional_value': float(total_notional),
                'positions': [
                    {
                        'symbol': pos.symbol,
                        'side': pos.side,
                        'size': float(pos.size),
                        'entry_price': float(pos.entry_price),
                        'mark_price': float(pos.mark_price),
                        'pnl': float(pos.pnl),
                        'notional': float(pos.notional)
                    }
                    for pos in positions
                ]
            }
            
            logger.info(f"Position summary: {len(positions)} positions, Total PnL: ${total_pnl:.2f}")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate position summary: {e}", exc_info=True)
            return {
                'total_positions': 0,
                'long_positions': 0,
                'short_positions': 0,
                'total_unrealized_pnl': 0.0,
                'total_notional_value': 0.0,
                'positions': [],
                'error': str(e)
            }

# Singleton instance
exchange_manager = ExchangeManager()
