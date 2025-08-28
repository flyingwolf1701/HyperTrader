"""
FIXED WebSocket client that ignores historical/buffered trades
"""
import json
import asyncio
import websockets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Any
from loguru import logger
from .models import UnitTracker


class FixedHyperliquidWebSocketClient:
    """Fixed WebSocket client that doesn't process old trades"""
    
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.base_url = "wss://api.hyperliquid-testnet.xyz/ws" if testnet else "wss://api.hyperliquid.xyz/ws"
        self.ws_url = self.base_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.unit_trackers: Dict[str, UnitTracker] = {}
        self.price_callbacks: Dict[str, callable] = {}
        
        # Track connection time to ignore historical data
        self.connection_time: Optional[datetime] = None
        self.startup_grace_period = timedelta(seconds=5)  # Ignore first 5 seconds of data
        
        # Track last processed price to prevent duplicates
        self.last_processed_prices: Dict[str, Decimal] = {}
        self.last_processed_times: Dict[str, datetime] = {}
        
    async def connect(self):
        """Connect to WebSocket"""
        try:
            logger.info(f"Connecting to Hyperliquid WebSocket: {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            self.is_connected = True
            self.connection_time = datetime.now()
            logger.info("Successfully connected to Hyperliquid WebSocket")
            logger.info("Ignoring historical trades for 5 seconds...")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            return False
    
    async def subscribe_to_trades(self, symbol: str, unit_value: Decimal = Decimal("2.0"), 
                                 unit_tracker: UnitTracker = None, price_callback: callable = None) -> bool:
        """Subscribe to trade data for a symbol"""
        if not self.is_connected or not self.websocket:
            logger.error("WebSocket not connected. Call connect() first.")
            return False
        
        # Use provided tracker or create new one
        if unit_tracker:
            self.unit_trackers[symbol] = unit_tracker
        else:
            self.unit_trackers[symbol] = UnitTracker(unit_value=unit_value)
        
        # Store price callback if provided
        if price_callback:
            self.price_callbacks[symbol] = price_callback
        
        # Initialize tracking
        self.last_processed_prices[symbol] = Decimal("0")
        self.last_processed_times[symbol] = datetime.now()
        
        subscription_message = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": symbol
            }
        }
        
        try:
            await self.websocket.send(json.dumps(subscription_message))
            logger.info(f"Subscribed to {symbol} trades with unit value ${unit_value}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to {symbol} trades: {e}")
            return False
    
    async def listen(self):
        """Main listening loop with protection against historical data"""
        if not self.is_connected or not self.websocket:
            logger.error("WebSocket not connected.")
            return
        
        logger.info("Starting WebSocket listener...")
        
        try:
            async for message in self.websocket:
                await self._process_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {e}")
            self.is_connected = False
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message with timing validation"""
        try:
            data = json.loads(message)
            
            # Handle trades data
            if data.get("channel") == "trades":
                await self._handle_trades_fixed(data)
            # Handle subscription confirmations
            elif "method" in data and data.get("method") == "subscription":
                logger.debug(f"Subscription confirmed")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _handle_trades_fixed(self, data: dict):
        """Handle trade data with protection against historical/duplicate data"""
        if "data" not in data or len(data["data"]) == 0:
            return
        
        # Check if we're still in startup grace period
        if self.connection_time:
            time_since_connect = datetime.now() - self.connection_time
            if time_since_connect < self.startup_grace_period:
                # Still in grace period, ignore trades
                return
        
        trades = data["data"]
        
        # Process only the most recent trade (last in array)
        # This prevents processing multiple historical trades at once
        if trades:
            latest_trade = trades[-1]  # Take only the last (most recent) trade
            
            coin = latest_trade.get("coin")
            price_str = latest_trade.get("px")
            
            if coin and price_str and coin in self.unit_trackers:
                price = Decimal(price_str)
                current_time = datetime.now()
                
                # Check if this is a duplicate price (same price within 1 second)
                if coin in self.last_processed_prices:
                    last_price = self.last_processed_prices[coin]
                    last_time = self.last_processed_times[coin]
                    time_diff = (current_time - last_time).total_seconds()
                    
                    # Skip if same price within 1 second (likely duplicate)
                    if price == last_price and time_diff < 1:
                        return
                
                # Update last processed
                self.last_processed_prices[coin] = price
                self.last_processed_times[coin] = current_time
                
                # Get unit tracker for this symbol
                tracker = self.unit_trackers[coin]
                
                # Log current price periodically
                if not hasattr(tracker, 'last_log_time'):
                    tracker.last_log_time = current_time
                    logger.info(f"{coin}: ${price:.2f} (Unit: {tracker.current_unit})")
                else:
                    time_since_log = (current_time - tracker.last_log_time).total_seconds()
                    if time_since_log >= 30:  # Log every 30 seconds
                        logger.info(f"{coin}: ${price:.2f} (Unit: {tracker.current_unit})")
                        tracker.last_log_time = current_time
                
                # Calculate unit change
                unit_changed = tracker.calculate_unit_change(price)
                
                # Handle unit change
                if unit_changed:
                    logger.info(f"{coin} UNIT CHANGE: {tracker.current_unit} at ${price:.2f}")
                    
                    # Call price callback if registered (with rate limiting)
                    if coin in self.price_callbacks:
                        # Check if callback was called recently
                        if not hasattr(tracker, 'last_callback_time'):
                            tracker.last_callback_time = datetime.min
                        
                        time_since_callback = (current_time - tracker.last_callback_time).total_seconds()
                        if time_since_callback >= 5:  # Minimum 5 seconds between callbacks
                            tracker.last_callback_time = current_time
                            asyncio.create_task(self.price_callbacks[coin](price))
                        else:
                            logger.debug(f"Skipping callback - too soon ({time_since_callback:.1f}s since last)")
    
    async def disconnect(self):
        """Close WebSocket connection"""
        self.is_connected = False
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
        logger.info("Disconnected from Hyperliquid WebSocket")