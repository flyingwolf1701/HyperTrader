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

from src.core.models import UnitTracker
from src.utils import settings


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
    
    async def subscribe_to_trades(self, symbol: str, unit_size_usd: Decimal = Decimal("2.0"), unit_tracker: UnitTracker = None, price_callback: callable = None) -> bool:
        """Subscribe to trade data for a symbol and initialize unit tracking"""
        if not self.is_connected or not self.websocket:
            logger.error("WebSocket not connected. Call connect() first.")
            return False
        
        # Use provided tracker or create new one
        if unit_tracker:
            self.unit_trackers[symbol] = unit_tracker
        else:
            self.unit_trackers[symbol] = UnitTracker(unit_size_usd=unit_size_usd)
        
        # Store price callback if provided (can be None initially)
        if price_callback:
            self.price_callbacks[symbol] = price_callback
        elif symbol not in self.price_callbacks:
            # Initialize with None if no callback provided yet
            self.price_callbacks[symbol] = None
        
        subscription_message = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": symbol
            }
        }
        
        try:
            await self.websocket.send(json.dumps(subscription_message))
            logger.info(f"Subscribed to {symbol} trades with unit size ${unit_size_usd}")
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
        last_message_time = datetime.now()
        
        while self.is_connected:
            try:
                # Set up ping task to keep connection alive
                ping_task = asyncio.create_task(self._ping_loop())
                
                # Set up connection monitoring task
                monitor_task = asyncio.create_task(self._connection_monitor())
                
                # Main message loop
                async for message in self.websocket:
                    last_message_time = datetime.now()
                    await self._process_message(message)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("🔌 WebSocket connection closed")
                ping_task.cancel()
                if 'monitor_task' in locals():
                    monitor_task.cancel()
                
                if reconnect_attempts < max_reconnect_attempts:
                    reconnect_attempts += 1
                    logger.warning(f"🔄 Attempting reconnect... ({reconnect_attempts}/{max_reconnect_attempts})")
                    
                    # Wait before reconnecting
                    await asyncio.sleep(5)
                    
                    # Try to reconnect
                    if await self._reconnect():
                        reconnect_attempts = 0
                        logger.success("✅ Reconnection successful")
                        continue
                    else:
                        logger.error("❌ Reconnection failed")
                else:
                    logger.error("🚨 Max reconnection attempts reached - CONNECTION LOST!")
                    self.is_connected = False
                    break
                    
            except Exception as e:
                logger.error(f"🚨 Error in WebSocket listener: {e}")
                if ping_task and not ping_task.done():
                    ping_task.cancel()
                if 'monitor_task' in locals() and not monitor_task.done():
                    monitor_task.cancel()
                self.is_connected = False
                break
                
        logger.warning("🛑 WebSocket listener stopped")
    
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
                
    async def _connection_monitor(self):
        """Monitor connection health and detect stale connections"""
        last_trade_time = datetime.now()
        
        while self.is_connected:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check if we haven't received trades in 2+ minutes
                time_since_last = datetime.now() - last_trade_time
                if time_since_last.total_seconds() > 120:
                    logger.warning(f"🚨 No trades received for {time_since_last.total_seconds():.0f}s")
                    logger.warning("📡 Connection may be stale - forcing reconnect")
                    # Force reconnection by closing current connection
                    if self.websocket:
                        await self.websocket.close()
                    break
                else:
                    # Update last trade time from websocket activity
                    if hasattr(self, '_last_message_time'):
                        last_trade_time = self._last_message_time
                        
            except Exception as e:
                logger.error(f"Connection monitor error: {e}")
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
            self._last_message_time = datetime.now()  # Track for connection monitoring
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
        """Handle trade data and update unit tracking - FIXED VERSION WITH RATE LIMITING"""
        if "data" not in data or len(data["data"]) == 0:
            return
            
        trades = data["data"]
        
        # CRITICAL FIX: Only process the LAST trade to prevent rapid oscillation
        # Processing every trade in the batch was causing the unit calculation chaos
        if trades:
            trade = trades[-1]  # Only process the most recent trade
            coin = trade.get("coin")
            price_str = trade.get("px")
            size_str = trade.get("sz", "0")
            
            if coin and price_str and coin in self.unit_trackers:
                price = Decimal(price_str)
                size = Decimal(size_str)
                timestamp = datetime.now().strftime('%H:%M:%S')
                
                # Get unit tracker for this symbol
                tracker = self.unit_trackers[coin]
                
                # Check for unit changes
                unit_changed = tracker.calculate_unit_change(price)
                
                # Simple periodic logging (every 60 seconds)
                if not hasattr(tracker, 'last_logged_time'):
                    tracker.last_logged_time = datetime.now()
                    if tracker.entry_price:
                        logger.info(f"💹 {coin} tracking started at ${tracker.entry_price:.2f}")
                else:
                    time_since_log = (datetime.now() - tracker.last_logged_time).total_seconds()
                    if time_since_log >= 60:  # Every 60 seconds
                        logger.info(f"💹 {coin}: ${price:.2f} | Unit: {tracker.current_unit}")
                        tracker.last_logged_time = datetime.now()
                
                # Unit change handling (already logged in UnitTracker)
                if unit_changed:
                    logger.warning(f"🚨 {coin} UNIT CHANGE DETECTED!")
                    self._log_phase_info(coin, tracker)
                    
                    # Call price callback if registered and not None
                    if coin in self.price_callbacks and self.price_callbacks[coin] is not None:
                        asyncio.create_task(self.price_callbacks[coin](price))
                        
                # Add periodic heartbeat for connection verification
                if not hasattr(self, '_last_heartbeat_time'):
                    self._last_heartbeat_time = datetime.now()
                    
                # Log heartbeat every 2 minutes to confirm connection
                time_since_heartbeat = datetime.now() - self._last_heartbeat_time
                if time_since_heartbeat.total_seconds() >= 120:
                    logger.info(f"💓 Connection alive - Last {coin} trade: ${price:.2f}")
                    self._last_heartbeat_time = datetime.now()
    
    def _log_phase_info(self, coin: str, tracker: UnitTracker):
        """Log phase-relevant information after unit change"""
        logger.info(
            f"{coin} Phase Info - "
            f"Phase: {tracker.phase.value} | "
            f"Peak: {tracker.peak_unit} | Valley: {tracker.valley_unit} | "
            f"Units from Peak: {tracker.get_units_from_peak()} | "
            f"Units from Valley: {tracker.get_units_from_valley()}"
        )