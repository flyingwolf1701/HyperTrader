"""
WebSocket client for HyperLiquid, refactored to use the official Hyperliquid SDK.
This approach simplifies connection management, authentication, and message handling.
"""
import asyncio
from decimal import Decimal
from typing import Dict, Callable, Any, Coroutine, Optional
from eth_account.signers.local import LocalAccount
from loguru import logger

from hyperliquid.ws_client import WsClient

class HyperliquidSDKClient:
    """A WebSocket client that wraps the Hyperliquid SDK's WsClient."""

    def __init__(self, account: LocalAccount, testnet: bool = True):
        """
        Initializes the SDK-based WebSocket client.

        Args:
            account: An eth_account.LocalAccount object for authentication.
            testnet: A boolean indicating whether to connect to the testnet.
        """
        self.account: LocalAccount = account
        self.ws_client: WsClient = WsClient(account, testnet=testnet)
        
        # Callbacks for processing different types of events
        self.price_callbacks: Dict[str, Callable[[Decimal], Coroutine]] = {}
        self.fill_callback: Optional[Callable[..., Coroutine]] = None
        self.order_callback: Optional[Callable[[Dict], Coroutine]] = None
        self.cancel_callback: Optional[Callable[[Dict], Coroutine]] = None

    async def connect(self):
        """Establishes the WebSocket connection using the SDK."""
        logger.info("Connecting to Hyperliquid WebSocket via SDK...")
        await self.ws_client.connect()
        logger.success("Successfully connected to Hyperliquid WebSocket.")

    async def disconnect(self):
        """Disconnects the WebSocket connection."""
        logger.info("Disconnecting from Hyperliquid WebSocket...")
        await self.ws_client.disconnect()
        logger.warning("Disconnected.")

    async def subscribe_to_trades(self, symbol: str, price_callback: Callable[[Decimal], Coroutine]):
        """

        Subscribes to the public trades channel for a given symbol.

        Args:
            symbol: The asset symbol (e.g., "BTC").
            price_callback: An async function to call with the latest trade price.
        """
        self.price_callbacks[symbol] = price_callback
        subscription = {"type": "trades", "coin": symbol}
        await self.ws_client.subscribe(subscription)
        logger.info(f"Subscribed to trades for {symbol}")

    async def subscribe_to_user_events(self, 
                                     fill_callback: Callable[..., Coroutine],
                                     order_callback: Callable[[Dict], Coroutine],
                                     cancel_callback: Callable[[Dict], Coroutine]):
        """
        Subscribes to the private userEvents channel.
        The SDK handles authentication automatically.

        Args:
            fill_callback: An async function to handle order fill events.
            order_callback: An async function to handle new order confirmation events.
            cancel_callback: An async function to handle order cancellation events.
        """
        self.fill_callback = fill_callback
        self.order_callback = order_callback
        self.cancel_callback = cancel_callback

        subscription = {"type": "userEvents", "user": self.account.address}
        await self.ws_client.subscribe(subscription)
        logger.success(f"Subscribed to userEvents for address: {self.account.address}")

    def start_listening(self) -> asyncio.Task:
        """Starts the message listening loop as a background task."""
        logger.info("Starting SDK WebSocket listener...")
        return asyncio.create_task(self._listen_loop())

    async def _listen_loop(self):
        """Continuously listens for messages from the SDK's queue."""
        while self.ws_client.ws.open:
            try:
                message = await asyncio.wait_for(self.ws_client.messages.get(), timeout=120)
                await self._process_message(message)
            except asyncio.TimeoutError:
                logger.warning("No message received in 120 seconds. Connection may be stale.")
                # The SDK's internal heartbeat handles reconnection, but this is a useful log.
            except Exception as e:
                logger.error(f"Error in listener loop: {e}")
                break
        logger.warning("WebSocket listener loop has stopped.")

    async def _process_message(self, message: Dict[str, Any]):
        """
        Processes a single message and routes it to the appropriate callback.
        """
        channel = message.get("channel")
        data = message.get("data")

        if not data:
            return

        if channel == "trades":
            await self._handle_trades(data)
        elif channel == "userEvents":
            await self._handle_user_event(data)
        elif channel == "subscriptionResponse":
             logger.debug(f"Subscription confirmed: {data}")
        else:
             logger.trace(f"Received unhandled message on channel '{channel}': {data}")
    
    async def _handle_trades(self, trades_data: list):
        """Handles public trade messages."""
        if not trades_data:
            return
        
        # Process the most recent trade to avoid flooding
        latest_trade = trades_data[-1]
        coin = latest_trade.get("coin")
        price_str = latest_trade.get("px")

        if coin in self.price_callbacks and price_str:
            price = Decimal(price_str)
            await self.price_callbacks[coin](price)

    async def _handle_user_event(self, user_event_data: Dict[str, Any]):
        """Handles private user event messages."""
        event = user_event_data.get("event")
        if not event:
            return

        event_type = event.get("type")

        if event_type == "fill" and self.fill_callback:
            fill_data = event
            # Note: The SDK might structure the fill data slightly differently.
            # We are adapting it to match what your `handle_order_fill` expects.
            await self.fill_callback(
                order_id=str(fill_data.get("oid")),
                filled_price=Decimal(fill_data.get("px")),
                filled_size=Decimal(fill_data.get("sz"))
            )
        elif event_type == "order" and self.order_callback:
             await self.order_callback(event.get("order", {}))
        elif event_type == "cancel" and self.cancel_callback:
             await self.cancel_callback(event)
        # Can add handlers for 'liquidation', etc. here
