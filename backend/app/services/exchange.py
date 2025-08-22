import asyncio
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import ccxt.async_support as ccxt

from app.core.config import settings

logger = logging.getLogger(__name__)

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
            })

            if settings.HYPERLIQUID_TESTNET:
                self.exchange.set_sandbox_mode(True)
            
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
            balance = await self.exchange.fetch_balance()
            return balance.get('total', {})
        except Exception as e:
            logger.error(f"Could not fetch balances: {e}")
            return {}

# Singleton instance
exchange_manager = ExchangeManager()
