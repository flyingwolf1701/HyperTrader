import asyncio
import json
import logging
import websockets
from app.core.config import settings
from app.services.trading_logic import on_price_update

logger = logging.getLogger(__name__)

class MarketDataManager:
    def __init__(self):
        self.ws_url = "wss://api.hyperliquid.xyz/ws"
        self.symbol = settings.SYMBOL
        self._is_running = False
        self._task = None

    async def _listen(self):
        """
        The core listening loop. Connects, subscribes, and processes messages.
        Includes robust reconnection logic.
        """
        self._is_running = True
        logger.info(f"Starting to watch market data for {self.symbol}...")

        while self._is_running:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    # Subscribe to the L2 order book for the specified symbol
                    subscription_message = {
                        "method": "subscribe",
                        "subscription": {"type": "l2Book", "coin": self.symbol},
                    }
                    await websocket.send(json.dumps(subscription_message))
                    logger.info(f"Subscribed to l2Book for {self.symbol}")

                    # Process incoming messages from the exchange
                    async for message in websocket:
                        data = json.loads(message)
                        if data.get("channel") == "l2Book":
                            # Extract the best bid and ask to calculate the mid-price
                            levels = data.get("data", {}).get("levels", [])
                            if len(levels) == 2 and levels[0] and levels[1]:
                                best_bid = float(levels[0][0]["px"])
                                best_ask = float(levels[1][0]["px"])
                                mid_price = (best_bid + best_ask) / 2.0
                                
                                # Pass the new price to the trading logic service
                                await on_price_update(mid_price)

            except (websockets.ConnectionClosed, websockets.InvalidURI, ConnectionRefusedError) as e:
                logger.warning(f"WebSocket connection error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"An unexpected error occurred in _listen: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    
    def start(self):
        """Starts the listening task in the background."""
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._listen())
            logger.info("MarketDataManager task created.")

    async def stop(self):
        """Stops the listening loop and cancels the background task."""
        logger.info("Stopping MarketDataManager...")
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Market data task successfully cancelled.")
        logger.info("MarketDataManager stopped.")


# Create a single, reusable instance of the manager
market_data_manager = MarketDataManager()
