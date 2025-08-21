# backend/app/services/exchange.py

import logging
from decimal import Decimal
from typing import Literal, Optional, List # <-- 1. IMPORT 'List'
import asyncio
from pydantic import BaseModel

# This import is correct, even if some linters have trouble finding the submodule.
import ccxt.async_support as ccxt

from app.core.config import settings

logger = logging.getLogger(__name__)

class MarketInfo(BaseModel):
    """Market information structure."""
    symbol: str
    base: str
    quote: str
    active: bool
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None

class OrderResult(BaseModel):
    """Standardized result for order placement."""
    success: bool
    order_id: Optional[str] = None
    cost: Optional[Decimal] = None
    error_message: Optional[str] = None

class ExchangeManager:
    """
    Asynchronous manager for interacting with the Hyperliquid exchange.
    Uses the free version of the CCXT library in async mode.
    """
    def __init__(self):
        self.exchange: Optional[ccxt.hyperliquid] = None

    async def initialize(self):
        """Initializes the asynchronous exchange instance."""
        if self.exchange:
            logger.warning("Exchange manager already initialized.")
            return

        try:
            exchange_class = getattr(ccxt, 'hyperliquid')
            self.exchange = exchange_class({
                'walletAddress': settings.HYPERLIQUID_API_KEY,  # HyperLiquid uses walletAddress
                'privateKey': settings.HYPERLIQUID_SECRET_KEY,
                'enableRateLimit': True,
            })
            
            # --- 2. ADDED SAFETY CHECKS ---
            # Ensure the exchange object was created before using it.
            if not self.exchange:
                raise Exception("Exchange object could not be created.")

            if settings.HYPERLIQUID_TESTNET:
                self.exchange.set_sandbox_mode(True)
            
            await self.exchange.load_markets()
            logger.info(f"ExchangeManager initialized with {len(self.exchange.markets)} markets.")
        except Exception as e:
            logger.error(f"Failed to initialize ExchangeManager: {e}", exc_info=True)
            raise

    async def close(self):
        """Closes the exchange connection."""
        if self.exchange:
            await self.exchange.close()
            self.exchange = None
            logger.info("Exchange connection closed.")

    def _amount_to_precision(self, symbol: str, amount: float) -> float:
        """Convert amount to exchange precision requirements."""
        try:
            result = self.exchange.amount_to_precision(symbol, amount)
            return float(result)
        except Exception as e:
            logger.error(f"Failed to format amount precision: {e}")
            return amount

    def _price_to_precision(self, symbol: str, price: float) -> float:
        """Convert price to exchange precision requirements."""
        try:
            result = self.exchange.price_to_precision(symbol, price)
            return float(result)
        except Exception as e:
            logger.error(f"Failed to format price precision: {e}")
            return price

    async def place_order(
        self, 
        symbol: str, 
        order_type: Literal["market", "limit"], 
        side: Literal["buy", "sell"], 
        amount: float, 
        price: Optional[float] = None,
        reduce_only: bool = False
    ) -> OrderResult:
        if not self.exchange:
            return OrderResult(success=False, error_message="Exchange not initialized.")

        for attempt in range(3):
            try:
                # Format amount with proper precision
                formatted_amount = self._amount_to_precision(symbol, amount)
                
                # For HyperLiquid market orders, get price from markets
                if order_type == "market" and price is None:
                    current_price = await self.get_current_price(symbol)
                    if current_price is None:
                        raise Exception(f"Could not get current price for {symbol}")
                    price = float(current_price)
                
                # Format price with proper precision
                formatted_price = self._price_to_precision(symbol, price)
                
                params = {'reduceOnly': reduce_only}
                
                logger.info(f"Placing {side} {order_type} order: {formatted_amount} {symbol} at ${formatted_price}")
                
                order = await self.exchange.create_order(
                    symbol, order_type, side, formatted_amount, formatted_price, params
                )
                logger.info(f"Successfully placed {side} {order_type} order for {formatted_amount} {symbol}.")
                return OrderResult(
                    success=True, 
                    order_id=order.get('id'),
                    cost=Decimal(str(order.get('cost', '0.0'))),
                    average_price=Decimal(str(order.get('average', formatted_price)))
                )
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Failed to place order: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        
        return OrderResult(success=False, error_message="Failed to place order after multiple attempts.")

    async def fetch_balance(self) -> Optional[Decimal]:
        # --- 3. REFORMATTED FOR STYLE ---
        if not self.exchange:
            return None
        try:
            balance_info = await self.exchange.fetch_balance()
            return Decimal(str(balance_info.get('USDC', {}).get('total', '0.0')))
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return None

    async def fetch_all_balances(self) -> dict:
        """Get all account balances"""
        if not self.exchange:
            return {}
        try:
            balance_info = await self.exchange.fetch_balance()
            logger.info(f"Raw balance info: {balance_info}")
            
            # HyperLiquid specific balance access based on reference code
            balances = {}
            
            # Check if balance_info has 'total' key with nested currencies
            if 'total' in balance_info and isinstance(balance_info['total'], dict):
                for currency, amount in balance_info['total'].items():
                    if float(amount) > 0:
                        balances[currency] = {
                            'total': float(amount),
                            'free': float(balance_info.get('free', {}).get(currency, 0)),
                            'used': float(balance_info.get('used', {}).get(currency, 0))
                        }
            else:
                # Fallback to standard format
                for currency, details in balance_info.items():
                    if isinstance(details, dict):
                        total = details.get('total', 0)
                        free = details.get('free', 0)
                        used = details.get('used', 0)
                        
                        if total > 0 or free > 0 or used > 0:
                            balances[currency] = {
                                'total': float(total),
                                'free': float(free),
                                'used': float(used)
                            }
            
            return balances
        except Exception as e:
            logger.error(f"Failed to fetch all balances: {e}")
            return {}

    async def fetch_positions(self, symbol: str) -> List[dict]:
        if not self.exchange:
            return []
        try:
            positions = await self.exchange.fetch_positions([symbol])
            return [p for p in positions if p.get('contracts') and float(p['contracts']) != 0]
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        if not self.exchange:
            return False
        try:
            await self.exchange.set_leverage(leverage, symbol)
            logger.info(f"Set leverage for {symbol} to {leverage}x.")
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            return False

    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current price for a symbol using HyperLiquid's midPx."""
        if not self.exchange:
            return None
        try:
            # Load markets to get midPx (HyperLiquid specific)
            markets = await self.exchange.load_markets()
            if symbol in markets:
                mid_price = markets[symbol]["info"]["midPx"]
                return Decimal(str(mid_price)) if mid_price else None
            else:
                logger.error(f"Symbol {symbol} not found in markets")
                return None
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            return None

    async def fetch_markets(self) -> List[MarketInfo]:
        """Get all available markets."""
        if not self.exchange:
            return []
        try:
            markets = await self.exchange.load_markets()
            market_list = []
            for symbol, market in markets.items():
                market_info = MarketInfo(
                    symbol=symbol,
                    base=market['base'],
                    quote=market['quote'],
                    active=market['active'],
                    min_amount=Decimal(str(market['limits']['amount']['min'])) if market['limits']['amount']['min'] else None,
                    max_amount=Decimal(str(market['limits']['amount']['max'])) if market['limits']['amount']['max'] else None,
                    min_price=Decimal(str(market['limits']['price']['min'])) if market['limits']['price']['min'] else None,
                    max_price=Decimal(str(market['limits']['price']['max'])) if market['limits']['price']['max'] else None,
                )
                market_list.append(market_info)
            return market_list
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    def is_market_available(self, symbol: str) -> bool:
        """Check if a market is available."""
        if not self.exchange or not self.exchange.markets:
            return False
        return symbol in self.exchange.markets and self.exchange.markets[symbol]['active']

    def get_market_info(self, symbol: str) -> Optional[MarketInfo]:
        """Get market info for a specific symbol."""
        if not self.exchange or not self.exchange.markets or symbol not in self.exchange.markets:
            return None
        
        market = self.exchange.markets[symbol]
        return MarketInfo(
            symbol=symbol,
            base=market['base'],
            quote=market['quote'],
            active=market['active'],
            min_amount=Decimal(str(market['limits']['amount']['min'])) if market['limits']['amount']['min'] else None,
            max_amount=Decimal(str(market['limits']['amount']['max'])) if market['limits']['amount']['max'] else None,
            min_price=Decimal(str(market['limits']['price']['min'])) if market['limits']['price']['min'] else None,
            max_price=Decimal(str(market['limits']['price']['max'])) if market['limits']['price']['max'] else None,
        )

exchange_manager = ExchangeManager()
