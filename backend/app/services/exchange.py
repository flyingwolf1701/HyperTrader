# backend/app/services/exchange.py

import ccxt.async_support as ccxt
from app.core.config import settings
from app.models.state import SystemState
from decimal import Decimal

class ExchangeManager:
    """
    A wrapper around the CCXT library to handle all interactions with the exchange.
    This keeps exchange-specific code isolated from the core trading logic.
    """
    def __init__(self):
        """
        Initializes the CCXT exchange instance with API keys and rate limiting enabled.
        """
        self.exchange = ccxt.hyperliquid({
            'apiKey': settings.HYPERLIQUID_API_KEY,
            'secret': settings.HYPERLIQUID_SECRET,
            'enableRateLimit': True,  # Crucial for preventing API bans
            'options': {
                'defaultType': 'spot', # Or 'future', 'swap' depending on what you trade
            },
        })

    async def close(self):
        """Closes the exchange connection."""
        await self.exchange.close()

    async def place_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None):
        """
        Places an order on the exchange.

        Args:
            symbol (str): The trading pair (e.g., 'BTC/USD').
            order_type (str): 'market' or 'limit'.
            side (str): 'buy' or 'sell'.
            amount (float): The quantity of the asset to trade.
            price (float, optional): The price for a limit order.

        Returns:
            dict: The order response from the exchange.
        """
        try:
            # Note: Leverage is often set via exchange-specific params
            params = {'leverage': 10} # Example, adjust as needed
            order = await self.exchange.create_order(symbol, order_type, side, amount, price, params)
            return order
        except Exception as e:
            # In a real app, use structured logging (e.g., loguru)
            print(f"Error placing order: {e}")
            raise

    async def fetch_markets(self):
        """
        Fetches all available trading pairs and their metadata from the exchange.
        """
        try:
            markets = await self.exchange.load_markets()
            # Here you could add logic to categorize by L1, etc.
            return markets
        except Exception as e:
            print(f"Error fetching markets: {e}")
            raise
            
    async def get_current_price(self, symbol: str) -> Decimal:
        """
        Fetches the current ticker price for a given symbol.

        Returns:
            Decimal: The last traded price.
        """
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return Decimal(str(ticker['last']))
        except Exception as e:
            print(f"Error fetching price for {symbol}: {e}")
            raise