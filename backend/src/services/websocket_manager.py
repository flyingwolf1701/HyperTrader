"""WebSocket manager for real-time market data."""

import asyncio
import json
import websockets
from typing import Dict, Any, Callable, Optional
from ..settings import settings


class WebSocketManager:
    """Manages WebSocket connections to HyperLiquid for real-time data."""
    
    def __init__(self):
        self.connection = None
        self.is_connected = False
        self.subscriptions = {}
        self.callbacks = {}
    
    async def connect(self):
        """Establish WebSocket connection."""
        try:
            self.connection = await websockets.connect(settings.hyperliquid_ws_url)
            self.is_connected = True
            print("WebSocket connected to HyperLiquid")
            
            # Start listening for messages
            asyncio.create_task(self._listen())
            
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            self.is_connected = False
    
    async def disconnect(self):
        """Close WebSocket connection."""
        if self.connection:
            await self.connection.close()
            self.is_connected = False
            print("WebSocket disconnected")
    
    async def subscribe_to_symbol(self, symbol: str, callback: Callable):
        """Subscribe to real-time price updates for a symbol."""
        # TODO: Implement HyperLiquid subscription format
        subscription_msg = {
            "method": "subscribe",
            "ch": f"trades.{symbol}",
            "id": len(self.subscriptions) + 1
        }
        
        if self.is_connected:
            await self.connection.send(json.dumps(subscription_msg))
            self.subscriptions[symbol] = subscription_msg["id"]
            self.callbacks[symbol] = callback
    
    async def _listen(self):
        """Listen for incoming WebSocket messages."""
        try:
            async for message in self.connection:
                data = json.loads(message)
                await self._handle_message(data)
        except Exception as e:
            print(f"WebSocket listening error: {e}")
            self.is_connected = False
    
    async def _handle_message(self, data: Dict[str, Any]):
        """Handle incoming WebSocket messages."""
        # TODO: Parse HyperLiquid message format and route to callbacks
        print(f"Received WebSocket message: {data}")


# Global WebSocket manager instance
ws_manager = WebSocketManager()
