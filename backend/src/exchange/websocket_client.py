"""
WebSocket client for HyperLiquid using the official SDK.
The SDK's Info class has built-in WebSocket functionality via subscribe/unsubscribe.
"""
import asyncio
from decimal import Decimal
from typing import Dict, Callable, Any, Optional
from eth_account.signers.local import LocalAccount
from loguru import logger

from hyperliquid.info import Info


class HyperliquidSDKClient:
    """A WebSocket client that uses Hyperliquid SDK's Info class for subscriptions."""

    def __init__(self, account: LocalAccount, testnet: bool = True):
        """
        Initializes the SDK-based WebSocket client.

        Args:
            account: An eth_account.LocalAccount object for authentication.
            testnet: A boolean indicating whether to connect to the testnet.
        """
        self.account = account
        self.testnet = testnet
        self.info: Optional[Info] = None

        # Callbacks for processing different types of events
        self.price_callbacks: Dict[str, Callable[[Decimal], Any]] = {}
        self.fill_callback: Optional[Callable] = None
        self.order_callback: Optional[Callable] = None
        self.cancel_callback: Optional[Callable] = None

        # Task management
        self.listener_task: Optional[asyncio.Task] = None
        self.running = False

    async def connect(self):
        """Establishes the WebSocket connection using the SDK."""
        logger.info("Connecting to Hyperliquid WebSocket via SDK...")

        # Initialize Info with WebSocket support
        self.info = Info(not self.testnet, skip_ws=False)

        logger.success("Successfully initialized Hyperliquid WebSocket client.")

    async def disconnect(self):
        """Disconnects the WebSocket connection."""
        logger.info("Disconnecting from Hyperliquid WebSocket...")

        self.running = False

        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass

        if self.info:
            self.info.disconnect_websocket()

        logger.warning("Disconnected.")

    async def subscribe_to_trades(self, symbol: str, price_callback: Callable[[Decimal], Any]):
        """
        Subscribes to the public trades channel for a given symbol.

        Args:
            symbol: The asset symbol (e.g., "BTC").
            price_callback: A function to call with the latest trade price.
        """
        self.price_callbacks[symbol] = price_callback

        # Subscribe to trades using the SDK
        subscription = {"type": "trades", "coin": symbol}

        # The SDK's subscribe method returns a callback function
        def handle_trades(data):
            """Handle incoming trade data"""
            if data and isinstance(data, list) and len(data) > 0:
                latest_trade = data[-1]
                if "px" in latest_trade:
                    price = Decimal(str(latest_trade["px"]))
                    # Run callback in event loop if it's async
                    if asyncio.iscoroutinefunction(price_callback):
                        asyncio.create_task(price_callback(price))
                    else:
                        price_callback(price)

        self.info.subscribe(subscription, handle_trades)
        logger.info(f"Subscribed to trades for {symbol}")

    async def subscribe_to_user_events(self,
                                     fill_callback: Callable,
                                     order_callback: Callable,
                                     cancel_callback: Callable):
        """
        Subscribes to the private userEvents channel.

        Args:
            fill_callback: A function to handle order fill events.
            order_callback: A function to handle new order confirmation events.
            cancel_callback: A function to handle order cancellation events.
        """
        self.fill_callback = fill_callback
        self.order_callback = order_callback
        self.cancel_callback = cancel_callback

        # Subscribe to user events
        subscription = {"type": "userEvents", "user": self.account.address}

        def handle_user_events(data):
            """Handle incoming user event data"""
            if not data:
                return

            # Process different event types
            if isinstance(data, dict):
                self._process_user_event(data)
            elif isinstance(data, list):
                for event in data:
                    self._process_user_event(event)

        self.info.subscribe(subscription, handle_user_events)
        logger.success(f"Subscribed to userEvents for address: {self.account.address}")

    def _process_user_event(self, event_data: Dict):
        """Process a single user event"""
        if "fills" in event_data:
            # Process fills
            for fill in event_data["fills"]:
                if self.fill_callback:
                    order_id = str(fill.get("oid", ""))
                    price = Decimal(str(fill.get("px", 0)))
                    size = Decimal(str(fill.get("sz", 0)))

                    if asyncio.iscoroutinefunction(self.fill_callback):
                        asyncio.create_task(self.fill_callback(order_id, price, size))
                    else:
                        self.fill_callback(order_id, price, size)

        if "orders" in event_data and self.order_callback:
            # Process order updates
            for order in event_data["orders"]:
                if asyncio.iscoroutinefunction(self.order_callback):
                    asyncio.create_task(self.order_callback(order))
                else:
                    self.order_callback(order)

        if "cancels" in event_data and self.cancel_callback:
            # Process cancellations
            for cancel in event_data["cancels"]:
                if asyncio.iscoroutinefunction(self.cancel_callback):
                    asyncio.create_task(self.cancel_callback(cancel))
                else:
                    self.cancel_callback(cancel)

    def start_listening(self) -> asyncio.Task:
        """Starts the message listening loop as a background task."""
        logger.info("Starting SDK WebSocket listener...")
        self.running = True
        self.listener_task = asyncio.create_task(self._keep_alive_loop())
        return self.listener_task

    async def _keep_alive_loop(self):
        """Keep the connection alive and process events"""
        while self.running:
            try:
                # The SDK handles WebSocket messages internally via callbacks
                # We just need to keep the loop running
                await asyncio.sleep(30)  # Periodic check

                # Could add heartbeat or connection check here if needed

            except asyncio.CancelledError:
                logger.warning("Listener task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in keep-alive loop: {e}")
                await asyncio.sleep(5)

        logger.warning("WebSocket listener loop has stopped.")