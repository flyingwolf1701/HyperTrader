"""
WebSocket client for HyperLiquid - FIXED VERSION with proper heartbeat mechanism
Implements Hyperliquid's specific ping/pong heartbeat system
"""
import asyncio
import json
import websockets
from decimal import Decimal
from datetime import datetime
from typing import Optional
from loguru import logger

from backend.src.core.unitTracker import UnitTracker
from src.utils import settings


class HyperliquidWebSocketClient:
    """WebSocket client with CORRECT Hyperliquid heartbeat implementation"""
    
    def __init__(self, testnet: bool = True):
        self.ws_url = "wss://api.hyperliquid-testnet.xyz/ws" if testnet else "wss://api.hyperliquid.xyz/ws"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.unit_trackers = {}  # Dict[symbol, UnitTracker] for multiple symbols
        self.price_callbacks = {}  # Dict[symbol, callable] for price change callbacks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._last_pong_time = datetime.now()
        
    async def connect(self) -> bool:
        """Establish WebSocket connection"""
        try:
            logger.info(f"Connecting to Hyperliquid WebSocket: {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            self.is_connected = True
            self._last_pong_time = datetime.now()
            logger.info("Successfully connected to Hyperliquid WebSocket")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Close WebSocket connection"""
        self.is_connected = False
        
        # Cancel heartbeat task
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close WebSocket
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
        
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
        """Main listening loop with CORRECT Hyperliquid heartbeat implementation"""
        if not self.is_connected or not self.websocket:
            logger.error("WebSocket not connected.")
            return
        
        logger.info("Starting WebSocket listener with Hyperliquid heartbeat...")
        
        # Start heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        reconnect_attempts = 0
        max_reconnect_attempts = 5
        
        while self.is_connected:
            try:
                # Set up connection monitoring task
                monitor_task = asyncio.create_task(self._connection_monitor())
                
                # Main message loop
                async for message in self.websocket:
                    self._last_pong_time = datetime.now()  # Update activity time
                    await self._process_message(message)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("🔌 WebSocket connection closed")
                
                # Cancel tasks
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
                if 'monitor_task' in locals() and not monitor_task.done():
                    monitor_task.cancel()
                self.is_connected = False
                break
                
        # Cleanup
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        
        logger.warning("🛑 WebSocket listener stopped")
    
    async def _heartbeat_loop(self):
        """
        CORRECT Hyperliquid heartbeat implementation
        Sends {"method": "ping"} every 50 seconds (10 seconds before timeout)
        """
        while self.is_connected:
            try:
                await asyncio.sleep(50)  # 50 seconds - same as official Python SDK
                
                if not self.is_connected or not self.websocket:
                    break
                
                # Send Hyperliquid-specific ping
                ping_message = {"method": "ping"}
                await self.websocket.send(json.dumps(ping_message))
                logger.debug("💗 Sent Hyperliquid ping")
                
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
                break
                
    async def _connection_monitor(self):
        """Monitor connection health based on pong responses"""
        while self.is_connected:
            try:
                await asyncio.sleep(70)  # Check every 70 seconds
                
                # Check if we haven't received any activity in 90+ seconds
                time_since_activity = (datetime.now() - self._last_pong_time).total_seconds()
                if time_since_activity > 90:  # 30 seconds after expected pong
                    logger.warning(f"🚨 No server activity for {time_since_activity:.0f}s")
                    logger.warning("📡 Connection appears stale - forcing reconnect")
                    # Force reconnection by closing current connection
                    if self.websocket:
                        await self.websocket.close()
                    break
                        
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
            self._last_pong_time = datetime.now()
            
            # Restart heartbeat
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
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
        """Process incoming WebSocket message with CORRECT pong handling"""
        try:
            data = json.loads(message)
            
            # Handle Hyperliquid pong response
            if data.get("channel") == "pong":
                logger.debug("💗 Received Hyperliquid pong")
                self._last_pong_time = datetime.now()
                return
            
            # Handle trades data
            elif data.get("channel") == "trades":
                await self._handle_trades(data)
                
            # Handle subscription confirmations
            elif "method" in data and data.get("method") == "subscription":
                logger.info(f"Subscription confirmed: {data}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _handle_trades(self, data: dict):
        """Handle trade data and update unit tracking - RATE LIMITED VERSION"""
        if "data" not in data or len(data["data"]) == 0:
            return
            
        trades = data["data"]
        
        # CRITICAL FIX: Only process the LAST trade to prevent rapid oscillation
        if trades:
            trade = trades[-1]  # Only process the most recent trade
            coin = trade.get("coin")
            price_str = trade.get("px")
            
            if coin and price_str and coin in self.unit_trackers:
                price = Decimal(price_str)
                
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
                        logger.info(f"🔔 Calling strategy callback for {coin} at ${price}")
                        asyncio.create_task(self.price_callbacks[coin](Decimal(str(price))))
                        
                # Add periodic connection verification
                if not hasattr(self, '_last_heartbeat_log'):
                    self._last_heartbeat_log = datetime.now()
                    
                # Log connection status every 2 minutes
                time_since_heartbeat = datetime.now() - self._last_heartbeat_log
                if time_since_heartbeat.total_seconds() >= 120:
                    logger.info(f"💓 Connection healthy - Last {coin} trade: ${price:.2f}")
                    self._last_heartbeat_log = datetime.now()
    
    def _log_phase_info(self, coin: str, tracker: UnitTracker):
        """Log phase-relevant information after unit change"""
        logger.info(
            f"{coin} Phase Info - "
            f"Phase: {tracker.phase.value} | "
            f"Peak: {tracker.peak_unit} | Valley: {tracker.valley_unit} | "
            f"Units from Peak: {tracker.get_units_from_peak()} | "
            f"Units from Valley: {tracker.get_units_from_valley()}"
        )