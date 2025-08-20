"""Exchange integration service using CCXT."""

import ccxt
from typing import Dict, Any, Optional
from app.core.config import settings

class ExchangeService:
    """Service for exchange operations using CCXT."""
    
    def __init__(self):
        """Initialize exchange connection."""
        self.exchange = None
        self.connect()
    
    def connect(self):
        """Connect to exchange API."""
        try:
            # TODO: Configure specific exchange (e.g., hyperliquid)
            self.exchange = ccxt.binance({
                'apiKey': settings.exchange_api_key,
                'secret': settings.exchange_secret,
                'sandbox': settings.exchange_sandbox,
                'enableRateLimit': True,
            })
        except Exception as e:
            print(f"Failed to connect to exchange: {e}")
    
    async def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol."""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            print(f"Failed to get price for {symbol}: {e}")
            return None
    
    async def place_market_order(self, symbol: str, side: str, amount: float) -> Optional[Dict[str, Any]]:
        """Place market order."""
        try:
            order = await self.exchange.create_market_order(symbol, side, amount)
            return order
        except Exception as e:
            print(f"Failed to place {side} order for {symbol}: {e}")
            return None
    
    async def get_balance(self) -> Optional[Dict[str, Any]]:
        """Get account balance."""
        try:
            balance = await self.exchange.fetch_balance()
            return balance
        except Exception as e:
            print(f"Failed to get balance: {e}")
            return None
