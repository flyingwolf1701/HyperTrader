"""
WebSocket connection for real-time price feeds from HyperLiquid
Based on Stage 1 of the development plan
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Dict, Any
import websockets
from datetime import datetime

logger = logging.getLogger(__name__)


class HyperLiquidWebSocket:
    """Manages WebSocket connection to HyperLiquid for real-time price updates"""
    
    def __init__(self, testnet: bool = True):
        """
        Initialize WebSocket connection manager
        
        Args:
            testnet: Whether to connect to testnet (True) or mainnet (False)
        """
        self.ws_url = "wss://api.hyperliquid-testnet.xyz/ws" if testnet else "wss://api.hyperliquid.xyz/ws"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.subscriptions: Dict[str, Callable] = {}
        self.last_prices: Dict[str, float] = {}
        self.reconnect_delay = 5  # seconds
        
    async def connect(self):
        """Establish WebSocket connection"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.running = True
            logger.info(f"Connected to HyperLiquid WebSocket at {self.ws_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            return False
    
    async def disconnect(self):
        """Close WebSocket connection"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from HyperLiquid WebSocket")
    
    async def subscribe_to_trades(self, coin: str, callback: Optional[Callable] = None):
        """
        Subscribe to trade updates for a specific coin
        
        Args:
            coin: The coin symbol (e.g., "ETH", "BTC")
            callback: Optional callback function to handle price updates
        """
        if not self.websocket:
            logger.error("WebSocket not connected")
            return False
            
        # Store callback if provided
        if callback:
            self.subscriptions[coin] = callback
            
        # Send subscription message
        subscribe_msg = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": coin
            }
        }
        
        try:
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to trades for {coin}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to {coin}: {e}")
            return False
    
    async def subscribe_to_l2book(self, coin: str, callback: Optional[Callable] = None):
        """
        Subscribe to order book updates for a specific coin
        
        Args:
            coin: The coin symbol (e.g., "ETH", "BTC")
            callback: Optional callback function to handle price updates
        """
        if not self.websocket:
            logger.error("WebSocket not connected")
            return False
            
        # Store callback if provided
        if callback:
            self.subscriptions[f"{coin}_l2book"] = callback
            
        # Send subscription message
        subscribe_msg = {
            "method": "subscribe",
            "subscription": {
                "type": "l2Book",
                "coin": coin
            }
        }
        
        try:
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to L2 book for {coin}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to L2 book for {coin}: {e}")
            return False
    
    async def listen(self):
        """
        Main listening loop for WebSocket messages
        Processes incoming messages and triggers callbacks
        """
        if not self.websocket:
            logger.error("WebSocket not connected")
            return
            
        while self.running:
            try:
                message = await self.websocket.recv()
                await self.handle_message(message)
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed, attempting to reconnect...")
                await self.reconnect()
                
            except Exception as e:
                logger.error(f"Error in WebSocket listener: {e}")
                await asyncio.sleep(1)
    
    async def handle_message(self, message: str):
        """
        Process incoming WebSocket message
        
        Args:
            message: Raw JSON message from WebSocket
        """
        try:
            data = json.loads(message)
            
            # Handle different message types
            if "channel" in data:
                channel = data["channel"]
                
                if channel == "trades":
                    await self.handle_trades_message(data)
                elif channel == "l2Book":
                    await self.handle_l2book_message(data)
                else:
                    logger.debug(f"Unhandled channel: {channel}")
                    
            elif "method" in data and data["method"] == "subscription":
                logger.info(f"Subscription confirmed: {data}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def handle_trades_message(self, data: Dict[str, Any]):
        """
        Handle trades channel message
        
        Args:
            data: Parsed trade message data
        """
        try:
            if "data" in data and len(data["data"]) > 0:
                trades = data["data"]
                
                for trade in trades:
                    coin = trade.get("coin")
                    price = float(trade.get("px", 0))
                    size = float(trade.get("sz", 0))
                    timestamp = trade.get("time", datetime.now().isoformat())
                    
                    if coin and price > 0:
                        # Update last known price
                        self.last_prices[coin] = price
                        
                        # Log the price update
                        logger.info(f"[{timestamp}] {coin} Price: ${price:.2f} (Size: {size})")
                        
                        # Trigger callback if registered
                        if coin in self.subscriptions:
                            await self.trigger_callback(coin, price, timestamp)
                            
        except Exception as e:
            logger.error(f"Error handling trades message: {e}")
    
    async def handle_l2book_message(self, data: Dict[str, Any]):
        """
        Handle L2 order book message
        
        Args:
            data: Parsed order book message data
        """
        try:
            if "data" in data:
                book_data = data["data"]
                coin = book_data.get("coin")
                
                if "levels" in book_data:
                    levels = book_data["levels"]
                    
                    # Get best bid and ask
                    if len(levels) >= 2:
                        best_bid = float(levels[0][0]["px"]) if levels[0] else 0
                        best_ask = float(levels[1][0]["px"]) if levels[1] else 0
                        
                        if best_bid > 0 and best_ask > 0:
                            # Use mid price
                            mid_price = (best_bid + best_ask) / 2
                            
                            # Update last known price
                            self.last_prices[coin] = mid_price
                            
                            # Log the price update
                            timestamp = datetime.now().isoformat()
                            logger.debug(f"[{timestamp}] {coin} Mid Price: ${mid_price:.2f} (Bid: ${best_bid:.2f}, Ask: ${best_ask:.2f})")
                            
                            # Trigger callback if registered
                            callback_key = f"{coin}_l2book"
                            if callback_key in self.subscriptions:
                                await self.trigger_callback(callback_key, mid_price, timestamp)
                                
        except Exception as e:
            logger.error(f"Error handling L2 book message: {e}")
    
    async def trigger_callback(self, key: str, price: float, timestamp: str):
        """
        Trigger registered callback for price update
        
        Args:
            key: Subscription key
            price: Current price
            timestamp: Timestamp of update
        """
        if key in self.subscriptions:
            callback = self.subscriptions[key]
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(price, timestamp)
                else:
                    callback(price, timestamp)
            except Exception as e:
                logger.error(f"Error in callback for {key}: {e}")
    
    async def reconnect(self):
        """Attempt to reconnect to WebSocket"""
        self.running = False
        
        if self.websocket:
            await self.websocket.close()
            
        await asyncio.sleep(self.reconnect_delay)
        
        if await self.connect():
            # Resubscribe to all previous subscriptions
            for key in self.subscriptions.keys():
                if "_l2book" in key:
                    coin = key.replace("_l2book", "")
                    await self.subscribe_to_l2book(coin)
                else:
                    await self.subscribe_to_trades(key)
            
            self.running = True
            logger.info("Successfully reconnected and resubscribed")
    
    def get_last_price(self, coin: str) -> Optional[float]:
        """
        Get the last known price for a coin
        
        Args:
            coin: The coin symbol
            
        Returns:
            Last known price or None if not available
        """
        return self.last_prices.get(coin)


# Global WebSocket instance
websocket_manager = HyperLiquidWebSocket()


async def test_websocket():
    """Test function to demonstrate WebSocket functionality"""
    
    # Price update callback
    async def on_price_update(price: float, timestamp: str):
        print(f"Price Update: ${price:.2f} at {timestamp}")
    
    # Connect to WebSocket
    ws = HyperLiquidWebSocket(testnet=True)
    
    if await ws.connect():
        # Subscribe to ETH trades
        await ws.subscribe_to_trades("ETH", on_price_update)
        
        # Listen for 30 seconds
        listen_task = asyncio.create_task(ws.listen())
        await asyncio.sleep(30)
        
        # Disconnect
        await ws.disconnect()
        listen_task.cancel()
        
        print("Test completed")
    else:
        print("Failed to connect")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_websocket())