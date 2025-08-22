# backend/app/services/market_data.py

import asyncio
import json
import websockets
from app.services.trading_logic import on_price_update
from app.core.config import settings

class MarketDataManager:
    def __init__(self):
        self.ws_url = "wss://api.hyperliquid.xyz/ws"
        self.symbol = settings.SYMBOL
        self._is_running = False
        self._task = None

    async def _listen(self):
        """
        The core listening loop. Connects, subscribes, and processes messages.
        Includes reconnection logic.
        """
        self._is_running = True
        print(f"Starting to watch market data for {self.symbol}...")

        while self._is_running:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    # Subscribe to the L2 book for the specified symbol
                    subscription_message = {
                        "method": "subscribe",
                        "subscription": {"type": "l2Book", "coin": self.symbol},
                    }
                    await websocket.send(json.dumps(subscription_message))
                    print(f"Subscribed to l2Book for {self.symbol}")

                    # Process incoming messages
                    async for message in websocket:
                        data = json.loads(message)
                        if data.get("channel") == "l2Book":
                            # Extract the best bid and ask to find the mid-price
                            levels = data.get("data", {}).get("levels", [])
                            if len(levels) == 2 and levels[0] and levels[1]:
                                best_bid = float(levels[0][0]["px"])
                                best_ask = float(levels[1][0]["px"])
                                mid_price = (best_bid + best_ask) / 2.0
                                
                                # When a new price is derived, call the trading logic
                                await on_price_update(mid_price)

            except (websockets.ConnectionClosed, websockets.InvalidURI, ConnectionRefusedError) as e:
                print(f"WebSocket connection error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"An unexpected error occurred in _listen: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    
    def start(self):
        """Starts the listening task in the background."""
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._listen())
            print("MarketDataManager task created.")

    async def stop(self):
        """Stops the listening loop and cancels the task."""
        print("Stopping MarketDataManager...")
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                print("Market data task successfully cancelled.")
        print("MarketDataManager stopped.")


# Create a single instance of the manager
market_data_manager = MarketDataManager()
