"""
WebSocket client for HyperLiquid using the official SDK.
The SDK's Info class has built-in WebSocket functionality via subscribe/unsubscribe.
"""
import asyncio
from decimal import Decimal
from datetime import datetime
from typing import Dict, Callable, Any, Optional
from loguru import logger
from hyperliquid.info import Info


class HyperliquidSDKWebSocketClient:
    """A WebSocket client that uses Hyperliquid SDK's Info class for subscriptions."""

    def __init__(self, mainnet: bool = False, user_address: Optional[str] = None):
        """
        Initializes the SDK-based WebSocket client.

        Args:
            mainnet: Whether to use mainnet (True) or testnet (False) - matches SDK convention
            user_address: Optional wallet address for user-specific subscriptions.
        """
        self.mainnet = mainnet
        self.user_address = user_address
        self.info: Optional[Info] = None
        self.is_connected = False
        self.startup_time = datetime.now()  # Track when bot started to filter old fills

        # Callbacks for processing different types of events
        self.price_callbacks: Dict[str, Callable[[Decimal], Any]] = {}
        self.fill_callbacks: Dict[str, Callable] = {}
        self.order_update_callbacks: Dict[str, Callable] = {}

        # Task management
        self.listener_task: Optional[asyncio.Task] = None

        # Track last price log time for periodic logging
        self._last_price_log: Dict[str, datetime] = {}
        self._last_heartbeat_log = datetime.now()

    async def connect(self) -> bool:
        """Establishes the WebSocket connection using the SDK."""
        try:
            logger.info("Connecting to Hyperliquid WebSocket via SDK...")

            # Initialize Info with WebSocket support
            # SDK expects True for mainnet, False for testnet
            self.info = Info(self.mainnet, skip_ws=False)
            self.is_connected = True

            logger.success("Successfully connected to Hyperliquid WebSocket")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnects the WebSocket connection."""
        logger.info("Disconnecting from Hyperliquid WebSocket...")

        self.is_connected = False

        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass

        if self.info:
            # SDK handles WebSocket disconnection internally
            pass

        logger.info("Disconnected from Hyperliquid WebSocket")

    async def subscribe_to_order_updates(self, user_address: str, order_callback: callable = None) -> bool:
        """
        Subscribe to order updates (placements, cancellations, status changes).

        Args:
            user_address: The wallet address to monitor for order updates.
            order_callback: Optional callback for order update events.
        """
        if not self.is_connected or not self.info:
            logger.error("WebSocket not connected. Call connect() first.")
            return False

        try:
            # Store the callback
            if order_callback:
                self.order_update_callbacks[user_address] = order_callback

            # Subscribe to order updates using the SDK
            subscription = {"type": "orderUpdates", "user": user_address}

            def handle_order_updates(data):
                """Handle incoming order update data"""
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(self._handle_order_updates(data), loop)
                    else:
                        asyncio.run(self._handle_order_updates(data))
                except RuntimeError:
                    self._handle_order_updates_sync(data)

            self.info.subscribe(subscription, handle_order_updates)
            logger.info(f"Subscribed to order updates for address: {user_address}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to order updates: {e}")
            return False

    async def subscribe_to_user_fills(self, user_address: str) -> bool:
        """
        Subscribe to user fills (order executions).

        Args:
            user_address: The wallet address to monitor for fills.
        """
        if not self.is_connected or not self.info:
            logger.error("WebSocket not connected. Call connect() first.")
            return False

        try:
            # Store the address for potential resubscription
            self.user_address = user_address

            # Subscribe to user fills using the SDK
            subscription = {"type": "userFills", "user": user_address}

            def handle_user_fills(data):
                """Handle incoming user fill data"""
                # SDK runs callbacks in a thread without event loop
                # We need to schedule the coroutine in the main loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(self._handle_user_fills(data), loop)
                    else:
                        # If no loop is running, call synchronously
                        asyncio.run(self._handle_user_fills(data))
                except RuntimeError:
                    # No event loop in thread, process synchronously
                    self._handle_user_fills_sync(data)

            self.info.subscribe(subscription, handle_user_fills)
            logger.info(f"Subscribed to user fills for address: {user_address}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to user fills: {e}")
            return False

    async def subscribe_to_trades(self, symbol: str, price_callback: callable = None, fill_callback: callable = None) -> bool:
        """
        Subscribes to the public trades channel for a given symbol.

        Args:
            symbol: The asset symbol (e.g., "ETH").
            price_callback: A function to call with the latest trade price.
            fill_callback: A function to handle order fills for this symbol.
        """
        if not self.is_connected or not self.info:
            logger.error("WebSocket not connected. Call connect() first.")
            return False

        try:
            # Store callbacks
            if price_callback:
                self.price_callbacks[symbol] = price_callback

            if fill_callback:
                self.fill_callbacks[symbol] = fill_callback

            # Subscribe to trades using the SDK
            subscription = {"type": "trades", "coin": symbol}

            def handle_trades(data):
                """Handle incoming trade data"""
                # SDK runs callbacks in a thread without event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(self._handle_trades(symbol, data), loop)
                    else:
                        asyncio.run(self._handle_trades(symbol, data))
                except RuntimeError:
                    # No event loop in thread, process synchronously
                    self._handle_trades_sync(symbol, data)

            self.info.subscribe(subscription, handle_trades)
            logger.info(f"Subscribed to trades for {symbol}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to {symbol} trades: {e}")
            return False

    async def listen(self):
        """
        Main listening loop. The SDK handles WebSocket messages internally via callbacks.
        This method just keeps the connection alive.
        """
        if not self.is_connected or not self.info:
            logger.error("WebSocket not connected.")
            return

        logger.info("Starting WebSocket listener with Hyperliquid SDK...")

        # Create keep-alive task
        self.listener_task = asyncio.create_task(self._keep_alive_loop())

        try:
            # Keep the listener running
            await self.listener_task
        except asyncio.CancelledError:
            logger.info("WebSocket listener cancelled")
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {e}")
        finally:
            logger.warning("WebSocket listener stopped")

    async def _keep_alive_loop(self):
        """Keep the connection alive and let SDK handle events"""
        while self.is_connected:
            try:
                # The SDK handles WebSocket messages internally via callbacks
                # We just need to keep the loop running
                await asyncio.sleep(30)  # Periodic check

            except asyncio.CancelledError:
                logger.warning("Keep-alive loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in keep-alive loop: {e}")
                await asyncio.sleep(5)

    async def _handle_trades(self, symbol: str, data):
        """Handle incoming trade data"""
        try:
            # logger.info(f"RAW TRADE DATA ({symbol}): {data}")
            if not data:
                return

            # Extract trades from SDK response format {'channel': 'trades', 'data': [...]}
            if isinstance(data, dict) and 'data' in data:
                trades = data['data']
            else:
                trades = data if isinstance(data, list) else [data]
            # Process trades silently

            # Process only the last trade to prevent rapid updates
            if trades:
                trade = trades[-1]

                # Extract price from trade data
                price_str = trade.get("px")
                if price_str:
                    price = Decimal(str(price_str))
                    # Process price silently

                    # Call price callback if registered
                    if symbol in self.price_callbacks and self.price_callbacks[symbol]:
                        callback = self.price_callbacks[symbol]
                        # Call callback silently
                        # Handle both sync and async callbacks
                        if asyncio.iscoroutinefunction(callback):
                            await callback(price)
                        else:
                            callback(price)
                    else:
                        logger.warning(f"⚠️ No price callback registered for {symbol}")

                    # No periodic logging - only log on first connection
                    if symbol not in self._last_price_log:
                        self._last_price_log[symbol] = datetime.now()
                        logger.info(f"{symbol} price feed connected")

        except Exception as e:
            logger.error(f"Error handling trades for {symbol}: {e}")

    async def _handle_user_fills(self, data):
        """Handle incoming user fill data"""
        try:
            # logger.info(f"RAW USER DATA: {data}")
            if not data:
                return

            # The SDK might return fills in different formats
            fills = []
            if isinstance(data, dict):
                # Check for fills array within dict
                if "fills" in data:
                    fills = data["fills"]
                else:
                    fills = [data]
            elif isinstance(data, list):
                fills = data

            for fill in fills:
                if not isinstance(fill, dict):
                    continue

                # Extract fill information
                coin = fill.get("coin")
                px = fill.get("px")
                sz = fill.get("sz")
                side = fill.get("side")
                oid = fill.get("oid")
                time_ms = fill.get("time")

                # Filter out old fills from before bot startup
                if time_ms:
                    fill_time = datetime.fromtimestamp(time_ms / 1000)
                    if fill_time < self.startup_time:
                        logger.info(f"Skipping old fill from {fill_time} (before startup {self.startup_time})")
                        continue

                if coin and px and sz:
                    # Only process fills for symbols we're tracking
                    if coin not in self.fill_callbacks:
                        continue

                    price = Decimal(str(px))
                    size = abs(Decimal(str(sz)))
                    is_buy = side == "B" or float(sz) > 0

                    logger.warning(
                        f"ORDER FILL: {coin} {'BUY' if is_buy else 'SELL'} "
                        f"{size} @ ${price:.2f} (Order ID: {oid})"
                    )

                    # Call fill callback if registered
                    if self.fill_callbacks[coin]:
                        callback = self.fill_callbacks[coin]
                        logger.info(f"Triggering fill callback for {coin}")
                        logger.warning(f"📝 FILL CALLBACK: Passing order_id={oid} (type: {type(oid)})")

                        # Call with expected parameters
                        if asyncio.iscoroutinefunction(callback):
                            await callback(str(oid), price, size)
                        else:
                            callback(str(oid), price, size)

        except Exception as e:
            logger.error(f"Error handling user fills: {e}")

    def _handle_trades_sync(self, symbol: str, data):
        """Synchronous version of _handle_trades for thread context"""
        try:
            # logger.info(f"RAW SYNC TRADE DATA ({symbol}): {data}")
            if not data or not self.is_connected:
                return

            # Extract trades from SDK response format
            if isinstance(data, dict) and 'data' in data:
                trades = data['data']
            else:
                trades = data if isinstance(data, list) else [data]

            if trades:
                trade = trades[-1]
                price_str = trade.get("px")
                if price_str:
                    price = Decimal(str(price_str))

                    # Call price callback if registered (only if still connected)
                    if self.is_connected and symbol in self.price_callbacks and self.price_callbacks[symbol]:
                        try:
                            self.price_callbacks[symbol](price)
                        except Exception as e:
                            if "no running event loop" not in str(e).lower():
                                logger.error(f"Error calling price callback: {e}")

                    # No periodic logging in sync handler either
                    pass

        except Exception as e:
            logger.error(f"Error in sync trades handler for {symbol}: {e}")

    def _handle_user_fills_sync(self, data):
        """Synchronous version of _handle_user_fills for thread context"""
        try:
            # logger.info(f"RAW SYNC USER DATA: {data}")
            if not data:
                return

            fills = []
            if isinstance(data, dict):
                if "fills" in data:
                    fills = data["fills"]
                else:
                    fills = [data]
            elif isinstance(data, list):
                fills = data

            for fill in fills:
                if not isinstance(fill, dict):
                    continue

                coin = fill.get("coin")
                px = fill.get("px")
                sz = fill.get("sz")
                side = fill.get("side")
                oid = fill.get("oid")
                time_ms = fill.get("time")

                # Filter old fills
                if time_ms:
                    fill_time = datetime.fromtimestamp(time_ms / 1000)
                    if fill_time < self.startup_time:
                        continue

                if coin and px and sz:
                    if coin not in self.fill_callbacks:
                        continue

                    price = Decimal(str(px))
                    size = abs(Decimal(str(sz)))
                    is_buy = side == "B" or float(sz) > 0

                    logger.warning(
                        f"ORDER FILL: {coin} {'BUY' if is_buy else 'SELL'} "
                        f"{size} @ ${price:.2f} (Order ID: {oid})"
                    )

                    if self.fill_callbacks[coin]:
                        # Since we're in sync context, we can't await
                        # The callback should be sync in this case
                        self.fill_callbacks[coin](str(oid), price, size)

        except Exception as e:
            logger.error(f"Error in sync user fills handler: {e}")

    async def _handle_order_updates(self, data):
        """Handle incoming order update data"""
        try:
            if not data:
                return

            # Handle array of order updates
            orders = []
            if isinstance(data, dict) and "data" in data:
                orders = data["data"]
            elif isinstance(data, list):
                orders = data
            else:
                orders = [data]

            for order_data in orders:
                if not isinstance(order_data, dict):
                    continue

                # Extract order information from WsOrder format
                # WsOrder: {order: WsBasicOrder, status: string, statusTimestamp: number}
                order = order_data.get("order", {})
                status = order_data.get("status", "unknown")
                status_timestamp = order_data.get("statusTimestamp", 0)

                # Extract basic order info
                coin = order.get("coin")
                side = order.get("side")
                limit_px = order.get("limitPx")
                sz = order.get("sz")
                oid = order.get("oid")
                orig_sz = order.get("origSz")

                if coin and limit_px and sz:
                    # Log comprehensive order update
                    logger.warning(
                        f"[ORDER UPDATE] {status.upper()} | {coin} {side} "
                        f"{sz}/{orig_sz} @ ${limit_px} | OID: {oid}"
                    )

                    # Call callback if registered
                    for user_address, callback in self.order_update_callbacks.items():
                        if callback:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(order_data)
                            else:
                                callback(order_data)

        except Exception as e:
            logger.error(f"Error handling order updates: {e}")

    def _handle_order_updates_sync(self, data):
        """Synchronous version of _handle_order_updates for thread context"""
        try:
            if not data:
                return

            orders = []
            if isinstance(data, dict) and "data" in data:
                orders = data["data"]
            elif isinstance(data, list):
                orders = data
            else:
                orders = [data]

            for order_data in orders:
                if not isinstance(order_data, dict):
                    continue

                order = order_data.get("order", {})
                status = order_data.get("status", "unknown")

                coin = order.get("coin")
                side = order.get("side")
                limit_px = order.get("limitPx")
                sz = order.get("sz")
                oid = order.get("oid")
                orig_sz = order.get("origSz")

                if coin and limit_px and sz:
                    logger.warning(
                        f"[ORDER UPDATE] {status.upper()} | {coin} {side} "
                        f"{sz}/{orig_sz} @ ${limit_px} | OID: {oid}"
                    )

                    # Call callback if registered (sync only)
                    for user_address, callback in self.order_update_callbacks.items():
                        if callback and not asyncio.iscoroutinefunction(callback):
                            callback(order_data)

        except Exception as e:
            logger.error(f"Error in sync order updates handler: {e}")