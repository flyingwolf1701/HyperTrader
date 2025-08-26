"""
WebSocket client for HyperLiquid - Stage 1 & 2 Implementation
Handles real-time price feeds and unit tracking
"""
import asyncio
import json
import websockets
from decimal import Decimal
from datetime import datetime
from typing import Optional
from loguru import logger

try:
    from .models import UnitTracker
    from ..utils import settings
except ImportError:
    from core.models import UnitTracker
    from utils.config import settings


class HyperliquidWebSocketClient:
    """WebSocket client for real-time price tracking with unit change detection"""
    
    def __init__(self, testnet: bool = True):
        self.ws_url = "wss://api.hyperliquid-testnet.xyz/ws" if testnet else "wss://api.hyperliquid.xyz/ws"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.unit_trackers = {}  # Dict[symbol, UnitTracker] for multiple symbols
        self.price_callbacks = {}  # Dict[symbol, callable] for price change callbacks
        
    async def connect(self) -> bool:
        """Establish WebSocket connection"""
        try:
            logger.info(f"Connecting to Hyperliquid WebSocket: {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            self.is_connected = True
            logger.info("Successfully connected to Hyperliquid WebSocket")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Close WebSocket connection"""
        self.is_connected = False
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
        logger.info("Disconnected from Hyperliquid WebSocket")
    
    async def subscribe_to_trades(self, symbol: str, unit_size: Decimal = Decimal("2.0"), unit_tracker: UnitTracker = None, price_callback: callable = None) -> bool:
        """Subscribe to trade data for a symbol and initialize unit tracking"""
        if not self.is_connected or not self.websocket:
            logger.error("WebSocket not connected. Call connect() first.")
            return False
        
        # Use provided tracker or create new one
        if unit_tracker:
            self.unit_trackers[symbol] = unit_tracker
        else:
            self.unit_trackers[symbol] = UnitTracker(unit_size=unit_size)
        
        # Store price callback if provided
        if price_callback:
            self.price_callbacks[symbol] = price_callback
        
        subscription_message = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": symbol
            }
        }
        
        try:
            await self.websocket.send(json.dumps(subscription_message))
            logger.info(f"Subscribed to {symbol} trades with unit size ${unit_size}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to {symbol} trades: {e}")
            return False
    
    async def listen(self):
        """Main listening loop for processing WebSocket messages with auto-reconnect"""
        if not self.is_connected or not self.websocket:
            logger.error("WebSocket not connected.")
            return
        
        logger.info("Starting WebSocket listener...")
        
        reconnect_attempts = 0
        max_reconnect_attempts = 5
        
        while self.is_connected:
            try:
                # Set up ping task to keep connection alive
                ping_task = asyncio.create_task(self._ping_loop())
                
                # Main message loop
                async for message in self.websocket:
                    await self._process_message(message)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                ping_task.cancel()
                
                if reconnect_attempts < max_reconnect_attempts:
                    reconnect_attempts += 1
                    logger.info(f"Attempting to reconnect... (attempt {reconnect_attempts}/{max_reconnect_attempts})")
                    
                    # Wait before reconnecting
                    await asyncio.sleep(5)
                    
                    # Try to reconnect
                    if await self._reconnect():
                        reconnect_attempts = 0
                        logger.info("Reconnection successful")
                        continue
                    else:
                        logger.error("Reconnection failed")
                else:
                    logger.error("Max reconnection attempts reached")
                    self.is_connected = False
                    break
                    
            except Exception as e:
                logger.error(f"Error in WebSocket listener: {e}")
                if ping_task and not ping_task.done():
                    ping_task.cancel()
                self.is_connected = False
                break
    
    async def _ping_loop(self):
        """Send ping messages periodically to keep connection alive"""
        while self.is_connected:
            try:
                await asyncio.sleep(30)  # Ping every 30 seconds
                if self.websocket:
                    await self.websocket.ping()
                    # Removed debug logging for cleaner output
            except Exception as e:
                logger.warning(f"Ping failed: {e}")
                break
    
    async def _reconnect(self) -> bool:
        """Attempt to reconnect to WebSocket"""
        try:
            # Close existing connection if any
            if self.websocket:
                await self.websocket.close()
            
            # Connect again
            self.websocket = await websockets.connect(self.ws_url)
            self.is_connected = True
            
            # Re-subscribe to all symbols
            for symbol, tracker in self.unit_trackers.items():
                subscription_message = {
                    "method": "subscribe",
                    "subscription": {
                        "type": "trades",
                        "coin": symbol
                    }
                }
                await self.websocket.send(json.dumps(subscription_message))
                logger.info(f"Re-subscribed to {symbol} trades")
            
            return True
            
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Handle trades data
            if data.get("channel") == "trades":
                await self._handle_trades(data)
            # Handle subscription confirmations
            elif "method" in data and data.get("method") == "subscription":
                logger.info(f"Subscription confirmed: {data}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _handle_trades(self, data: dict):
        """Handle trade data and update unit tracking - IMPROVED VERSION"""
        if "data" not in data or len(data["data"]) == 0:
            return
            
        trades = data["data"]
        
        for trade in trades:
            coin = trade.get("coin")
            price_str = trade.get("px")
            size_str = trade.get("sz", "0")
            
            if coin and price_str and coin in self.unit_trackers:
                price = Decimal(price_str)
                size = Decimal(size_str)
                timestamp = datetime.now().strftime('%H:%M:%S')
                
                # Get unit tracker for this symbol
                tracker = self.unit_trackers[coin]
                
                # ONLY log meaningful price updates (every ~$5-10 or on unit changes)
                if not hasattr(tracker, 'last_logged_price'):
                    tracker.last_logged_price = price
                    logger.info(f"[{timestamp}] {coin}: ${price:.2f} (Unit: {tracker.current_unit})")
                else:
                    price_change = abs(price - tracker.last_logged_price)
                    if price_change >= Decimal("10.0"):  # Only log significant moves
                        logger.info(f"[{timestamp}] {coin}: ${price:.2f} (Unit: {tracker.current_unit})")
                        tracker.last_logged_price = price
                
                # Calculate unit change
                unit_changed = tracker.calculate_unit_change(price)
                
                # ONLY log when unit actually changes
                if unit_changed:
                    logger.warning(f"🚀 {coin} UNIT CHANGE: Unit {tracker.current_unit}")
                    self._log_phase_info(coin, tracker)
                    
                    # Call price callback if registered
                    if coin in self.price_callbacks:
                        asyncio.create_task(self.price_callbacks[coin](price))
    
    def _log_phase_info(self, coin: str, tracker: UnitTracker):
        """Log phase-relevant information after unit change"""
        logger.info(
            f"{coin} Phase Info - "
            f"Phase: {tracker.phase.value} | "
            f"Peak: {tracker.peak_unit} | Valley: {tracker.valley_unit} | "
            f"Units from Peak: {tracker.get_units_from_peak()} | "
            f"Units from Valley: {tracker.get_units_from_valley()}"
        )