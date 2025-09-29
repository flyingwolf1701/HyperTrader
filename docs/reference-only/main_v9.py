"""
HyperTrader Main Entry Point - Sliding Window Strategy v9.2.6
Integrates position map, unit tracker, SDK, and WebSocket for automated trading
"""

import asyncio
import sys
import os
from decimal import Decimal
from typing import Optional, Dict, List
from datetime import datetime
from loguru import logger

# Add src directory to path for absolute imports
src_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, src_dir)

# Import new strategy components
from strategy.data_models import (
    OrderType, Phase, ExecutionStatus, PositionState, 
    PositionConfig, UnitChangeEvent, OrderFillEvent
)
from strategy.position_map import (
    calculate_initial_position_map,
    add_unit_level,
    get_active_orders
)
from strategy.unit_tracker import UnitTracker
from exchange.hyperliquid_sdk import HyperliquidClient, OrderResult
from exchange.hyperliquid_sdk_websocket import HyperliquidSDKWebSocketClient
from exchange.wallet_config import WalletConfig, WalletType


class HyperTrader:
    """
    Main trading bot implementing sliding window strategy v9.2.6
    """
    
    def __init__(self, symbol: str = "ETH", wallet_type: str = "long", use_testnet: bool = True):
        """
        Initialize the HyperTrader bot
        
        Args:
            symbol: Trading symbol (e.g., "ETH")
            wallet_type: "long" or "hedge" wallet strategy
            use_testnet: Whether to use testnet
        """
        self.symbol = symbol
        self.wallet_type = wallet_type
        self.use_testnet = use_testnet
        
        # Initialize components
        self.sdk_client: Optional[HyperliquidClient] = None
        self.ws_client: Optional[HyperliquidSDKWebSocketClient] = None
        self.position_state: Optional[PositionState] = None
        self.position_map: Optional[Dict[int, PositionConfig]] = None
        self.unit_tracker: Optional[UnitTracker] = None
        
        # Trading parameters - must be set from command line
        self.unit_size_usd = None
        self.initial_position_size = None
        self.leverage = None
        
        # State tracking
        self.is_running = False
        self.current_price: Optional[Decimal] = None

        # Order ID to unit mapping for O(1) lookups
        self.order_id_to_unit: Dict[str, int] = {}

        logger.info(f"Initializing HyperTrader for {symbol} - {wallet_type} wallet")
    
    async def initialize(self):
        """Initialize all components and connections"""
        try:
            # Load wallet configuration from environment
            wallet_config = WalletConfig.from_env()

            # Initialize SDK client with explicit configuration
            # Map wallet_type string to WalletType
            wallet_type: WalletType = self.wallet_type  # type: ignore
            self.sdk_client = HyperliquidClient(
                config=wallet_config,
                wallet_type=wallet_type,
                use_testnet=self.use_testnet
            )
            logger.info(f"SDK client initialized for {self.wallet_type} wallet")
            
            # Get user address from SDK for order tracking
            user_address = self.sdk_client.get_user_address()
            
            # Initialize WebSocket client with user address
            self.ws_client = HyperliquidSDKWebSocketClient(
                testnet=self.use_testnet,
                user_address=user_address
            )
            connected = await self.ws_client.connect()
            if not connected:
                raise Exception("Failed to connect to WebSocket")
            logger.info("WebSocket client connected")
            
            # Subscribe to user fills for order execution tracking
            await self.ws_client.subscribe_to_user_fills(user_address)
            logger.info(f"Subscribed to order fills for address: {user_address}")
            
            # Get current market price
            self.current_price = await self._get_current_price()
            logger.info(f"Current {self.symbol} price: ${self.current_price:.2f}")
            
            # Initialize position if needed
            await self._initialize_position()
            
            # Subscribe to price updates with both price and fill callbacks
            await self.ws_client.subscribe_to_trades(
                symbol=self.symbol,
                price_callback=self._handle_price_update,
                fill_callback=self.handle_order_fill
            )
            
            logger.info("✅ HyperTrader initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize HyperTrader: {e}")
            return False
    
    async def _get_current_price(self) -> Decimal:
        """Get current market price from SDK"""
        return self.sdk_client.get_current_price(self.symbol)
    
    async def _initialize_position(self):
        """Initialize or load existing position"""
        logger.warning("🚀 ENTERING _initialize_position")

        # Check if we have an existing position
        logger.info("📊 Checking for existing positions...")
        positions = self.sdk_client.get_positions()
        logger.info(f"   Found positions for symbols: {list(positions.keys())}")

        if self.symbol in positions:
            # Load existing position
            position = positions[self.symbol]
            entry_price = position.entry_price
            asset_size = position.size
            logger.warning(f"✅ LOADED EXISTING POSITION: {asset_size} {self.symbol} @ ${entry_price:.2f}")
        else:
            # Create new position
            logger.warning(f"❌ NO EXISTING POSITION for {self.symbol} - Creating new one")

            estimated_price = self.current_price
            estimated_size = self.initial_position_size / estimated_price

            logger.warning(f"📈 CREATING NEW POSITION:")
            logger.warning(f"   Symbol: {self.symbol}")
            logger.warning(f"   Wallet type: {self.wallet_type}")
            logger.warning(f"   Current price: ${estimated_price:.2f}")
            logger.warning(f"   Position size USD: ${self.initial_position_size}")
            logger.warning(f"   Estimated asset size: {estimated_size:.6f} {self.symbol}")
            logger.warning(f"   Leverage: {self.leverage}x")

            # Place initial market buy order (for long wallet)
            if self.wallet_type == "long":
                logger.warning("🔥 PLACING INITIAL MARKET BUY ORDER...")
                result = await self._place_market_order("buy", estimated_size)

                logger.warning(f"📝 Market order result:")
                logger.warning(f"   Success: {result.success}")
                logger.warning(f"   Order ID: {result.order_id if result.success else 'N/A'}")
                logger.warning(f"   Error: {result.error_message if not result.success else 'None'}")

                if not result.success:
                    logger.error(f"❌ FAILED TO CREATE POSITION: {result.error_message}")
                    raise Exception(f"Failed to create initial position: {result.error_message}")

                # Track initial order ID to filter from fill matching
                self.initial_order_id = result.order_id
                logger.warning(f"✅ Initial position order placed! ID: {self.initial_order_id}")

                # CRITICAL: Wait for position to be fully established
                logger.info("⏳ Waiting for initial position to be fully established...")

                # Poll for position with timeout
                max_attempts = 30  # Increase timeout for slower fills
                for attempt in range(max_attempts):
                    await asyncio.sleep(2)  # Check every 2 seconds
                    positions = self.sdk_client.get_positions()

                    logger.info(f"   Attempt {attempt + 1}: Positions found: {list(positions.keys())}")

                    if self.symbol in positions:
                        logger.warning(f"✅ POSITION FOUND after {(attempt + 1) * 2} seconds")
                        break
                else:
                    logger.error(f"❌ Position not found after {max_attempts * 2} seconds")
                    logger.error(f"   Final positions check: {list(positions.keys())}")
                    raise Exception(f"Position not found after {max_attempts * 2} seconds")

                position = positions[self.symbol]
                entry_price = position.entry_price  # Use ACTUAL average fill price
                asset_size = position.size  # Use ACTUAL position size
                logger.warning(f"✅ POSITION ESTABLISHED: {asset_size:.6f} {self.symbol} @ ${entry_price:.2f} (actual fill price)")
            else:
                logger.error(f"❌ Wallet type '{self.wallet_type}' not supported for initial position")
                raise Exception(f"Wallet type '{self.wallet_type}' not supported")
        
        # Initialize position map with ACTUAL entry price
        self.position_state, self.position_map = calculate_initial_position_map(
            entry_price=entry_price,
            unit_size_usd=self.unit_size_usd,
            asset_size=asset_size,
            position_value_usd=asset_size * entry_price,  # Use actual position value
            unit_range=20  # Pre-calculate more units for sliding window
        )

        # Validate minimum spacing
        spacing_pct = (self.unit_size_usd / entry_price) * 100
        logger.info(f"📏 Unit spacing: ${self.unit_size_usd:.2f} = {spacing_pct:.3f}% of entry price ${entry_price:.2f}")

        # Log unit prices for verification
        units_to_check = [-4, -3, -2, -1, 0, 1, 2, 3, 4]
        logger.info("📊 Unit price verification:")
        for unit in units_to_check:
            if unit in self.position_map:
                price = self.position_map[unit].price
                logger.info(f"   Unit {unit:3d}: ${price:.4f}")

        # Initialize unit tracker with sliding window
        self.unit_tracker = UnitTracker(
            position_state=self.position_state,
            position_map=self.position_map
        )
        
        # Place initial sliding window orders
        await self._place_window_orders()

        logger.info(f"Position initialized with sliding window: {self.unit_tracker.get_window_state()}")

        # DO NOT validate/repair here - the initial setup is correct!
        logger.warning(f"✅ Initial window setup complete - Stops: {self.unit_tracker.trailing_stop}, Buys: {self.unit_tracker.trailing_buy}")
    
    async def _place_window_orders(self):
        """Place initial stop loss orders - BUT CHECK FOR EXISTING ORDERS FIRST"""

        # First, check what orders already exist
        open_orders = self.sdk_client.get_open_orders(self.symbol)
        logger.warning(f"🔍 Found {len(open_orders)} existing open orders")

        # Cancel ALL existing orders to start fresh
        if open_orders:
            logger.warning(f"🗑️ Cancelling {len(open_orders)} existing orders to start fresh...")
            for order in open_orders:
                order_id = order.get('oid')
                try:
                    self.sdk_client.cancel_order(self.symbol, order_id)
                    logger.info(f"   Cancelled order {order_id}")
                except Exception as e:
                    logger.error(f"   Failed to cancel order {order_id}: {e}")

            # Wait a moment for cancellations to process
            await asyncio.sleep(1)

        # Initialize with 4 stop-losses - CLOSEST FIRST (-1, -2, -3, -4)
        self.unit_tracker.trailing_stop = [-1, -2, -3, -4]
        self.unit_tracker.trailing_buy = []

        logger.warning(f"📋 INITIAL WINDOW STATE:")
        logger.warning(f"   trailing_stop: {self.unit_tracker.trailing_stop}")
        logger.warning(f"   trailing_buy: {self.unit_tracker.trailing_buy}")

        # Place stop losses at designated units - IN ORDER from -1 to -4
        order_ids = []
        for unit in [-1, -2, -3, -4]:  # Place in order, closest first
            if unit in self.position_map:
                # Clear any stale active state by marking as cancelled
                if self.position_map[unit].is_active:
                    self.position_map[unit].mark_cancelled()

                order_id = await self._place_stop_loss_order(unit)
                if order_id:
                    order_ids.append(order_id)

        logger.warning(f"✅ INITIAL SETUP COMPLETE - Placed {len(order_ids)} stop-loss orders")
        logger.warning(f"📋 Active position_map units: {[u for u, c in self.position_map.items() if c.is_active]}")
    
    async def _place_stop_order(self, unit: int, side: str) -> Optional[str]:
        """Place a stop order at a specific unit"""
        config = self.position_map[unit]
        price = config.price

        # Determine size based on fragment type
        if side == "sell":
            size = self.position_state.long_fragment_asset
            order_type = OrderType.STOP_LOSS_SELL
        else:
            # Calculate size in asset terms from USD fragment (adjusted for PnL in recovery)
            fragment_usd = self.unit_tracker.get_adjusted_fragment_usd()
            size = fragment_usd / price
            order_type = OrderType.STOP_BUY

        # Place order via SDK
        result = await self._sdk_place_stop_order(side, price, size)

        if result.success:
            # Update position map
            config.set_active_order(result.order_id, order_type)
            logger.info(f"Placed {side} stop order at unit {unit}: {size:.6f} @ ${price:.2f}")
            return result.order_id
        else:
            logger.error(f"Failed to place {side} stop order at unit {unit}: {result.error_message}")
            return None
    
    async def _place_stop_buy_order(self, unit: int) -> Optional[str]:
        """Place a stop buy order at a specific unit"""
        logger.warning(f"📊 ATTEMPTING TO PLACE STOP BUY at unit {unit}")

        # Debug for unit 0
        if unit == 0:
            logger.warning(f"🎯 Placing stop-buy at UNIT 0 (entry price)")
            logger.warning(f"🎯 Unit 0 in position_map: {0 in self.position_map}")

        if unit not in self.position_map:
            logger.error(f"❌ Unit {unit} not in position map! Available units: {sorted(self.position_map.keys())}")
            return None

        config = self.position_map[unit]

        # Check if order already active at this unit
        if config.is_active:
            logger.warning(f"⚠️ Order already active at unit {unit} (ID: {config.order_id}), skipping placement")
            return config.order_id

        price = config.price

        # Check for duplicate prices in active orders
        active_prices = []
        for u, cfg in self.position_map.items():
            if cfg.is_active and cfg.order_type == OrderType.STOP_BUY:
                active_prices.append((u, cfg.price))

        for other_unit, other_price in active_prices:
            if abs(other_price - price) < Decimal("0.01"):  # Within 1 cent
                logger.error(f"❌ Duplicate price detected! Unit {unit} price ${price:.2f} too close to unit {other_unit} price ${other_price:.2f}")
                return None

        # Use adjusted fragment in recovery phase (includes PnL reinvestment)
        fragment_usd = self.unit_tracker.get_adjusted_fragment_usd()
        size = fragment_usd / price

        logger.info(f"📊 Stop buy details: Unit {unit}, Price ${price:.2f}, Size {size:.6f} {self.symbol}, Value ${fragment_usd:.2f}")
        
        # Check if price is above current market
        current_market_price = await self._get_current_price()
        
        if price > current_market_price:
            # Price is above market - use stop limit buy
            logger.warning(f"🎯 Price ${price:.2f} > Market ${current_market_price:.2f} - Using STOP BUY")

            result = self.sdk_client.place_stop_buy(
                symbol=self.symbol,
                size=size,
                trigger_price=price,
                limit_price=price,  # Use same price for limit
                reduce_only=False  # Stop buys are for re-entry, not reduce-only
            )
            
            if result.success:
                config.set_active_order(result.order_id, OrderType.STOP_BUY)
                # Track order ID to unit mapping
                self.order_id_to_unit[result.order_id] = unit
                logger.warning(f"✅ STOP BUY SUCCESSFULLY PLACED at unit {unit} (triggers @ ${price:.2f})")
                logger.warning(f"📝 ORDER ID TRACKING: Stop buy at unit {unit} = {result.order_id}")
                return result.order_id
            else:
                logger.error(f"❌ STOP BUY FAILED at unit {unit}: {result.error_message}")
                return None
        else:
            # Price is at or below market - use LIMIT buy order
            logger.info(f"📉 Price ${price:.2f} <= Market ${current_market_price:.2f} - Using LIMIT BUY")

            result = self.sdk_client.place_limit_order(
                symbol=self.symbol,
                is_buy=True,
                price=price,
                size=size,
                reduce_only=False,
                post_only=True  # Maker order to avoid fees
            )

            if result.success:
                config.set_active_order(result.order_id, OrderType.STOP_BUY)  # Track as stop buy for strategy
                # Track order ID to unit mapping
                self.order_id_to_unit[result.order_id] = unit
                logger.warning(f"✅ LIMIT BUY SUCCESSFULLY PLACED at unit {unit} @ ${price:.2f}")
                logger.warning(f"📝 ORDER ID TRACKING: Limit buy at unit {unit} = {result.order_id}")
                return result.order_id
            else:
                logger.error(f"❌ LIMIT BUY FAILED at unit {unit}: {result.error_message}")
                return None
    
    async def _place_stop_loss_order(self, unit: int) -> Optional[str]:
        """Place a stop loss order at a specific unit"""

        # Debug for unit 0
        if unit == 0:
            logger.warning(f"🎯 Placing stop-loss at UNIT 0 (entry price)")
            logger.warning(f"🎯 Unit 0 in position_map: {0 in self.position_map}")

        if unit not in self.position_map:
            logger.error(f"❌ Unit {unit} not in position_map! Available units: {sorted(self.position_map.keys())}")
            return None

        config = self.position_map[unit]

        # Check if order already active at this unit
        if config.is_active:
            logger.warning(f"⚠️ Order already active at unit {unit} (ID: {config.order_id}), skipping placement")
            return config.order_id

        trigger_price = config.price

        # Check for duplicate prices in active orders
        active_prices = []
        for u, cfg in self.position_map.items():
            if cfg.is_active and cfg.order_type == OrderType.STOP_LOSS_SELL:
                active_prices.append((u, cfg.price))

        for other_unit, other_price in active_prices:
            if abs(other_price - trigger_price) < Decimal("0.01"):  # Within 1 cent
                logger.error(f"❌ Duplicate price detected! Unit {unit} price ${trigger_price:.2f} too close to unit {other_unit} price ${other_price:.2f}")
                return None

        # Stop losses are always sells that reduce the long position
        size = self.position_state.long_fragment_asset

        # Place stop order via SDK
        result = await self._sdk_place_stop_order("sell", trigger_price, size)

        if result.success:
            # Update position map
            config.set_active_order(result.order_id, OrderType.STOP_LOSS_SELL)
            # Track order ID to unit mapping
            self.order_id_to_unit[result.order_id] = unit
            logger.info(f"Placed STOP LOSS at unit {unit}: {size:.6f} {self.symbol} triggers @ ${trigger_price:.2f}")
            logger.warning(f"📝 ORDER ID TRACKING: Stop-loss at unit {unit} = {result.order_id}")
            return result.order_id
        else:
            logger.error(f"Failed to place stop loss at unit {unit}: {result.error_message}")
            return None
    
    
    async def _sdk_place_stop_order(self, side: str, trigger_price: Decimal, size: Decimal) -> OrderResult:
        """Place stop order via SDK"""
        is_buy = (side.lower() == "buy")
        # Stop SELLS should be reduce-only to prevent unwanted fills on price recovery
        # Stop BUYS are for re-entry and should NOT be reduce-only
        return self.sdk_client.place_stop_order(
            symbol=self.symbol,
            is_buy=is_buy,
            size=size,
            trigger_price=trigger_price,
            reduce_only=(not is_buy)  # Only stop sells are reduce-only
        )
    
    async def _place_market_order(self, side: str, size: Decimal) -> OrderResult:
        """Place market order via SDK"""
        is_buy = (side.lower() == "buy")

        logger.warning(f"🎯 _place_market_order called:")
        logger.warning(f"   Side: {side}")
        logger.warning(f"   Size: {size} {self.symbol}")

        # Calculate USD amount for the order
        current_price = await self._get_current_price()
        usd_amount = size * current_price

        logger.warning(f"   Current price: ${current_price:.2f}")
        logger.warning(f"   USD amount: ${usd_amount:.2f}")
        logger.warning(f"   Leverage: {self.leverage}x")
        logger.warning(f"   Is buy: {is_buy}")

        logger.warning(f"📞 Calling SDK open_position...")
        result = self.sdk_client.open_position(
            symbol=self.symbol,
            usd_amount=usd_amount,
            is_long=is_buy,
            leverage=self.leverage,
            slippage=0.01
        )

        logger.warning(f"📋 SDK open_position result:")
        logger.warning(f"   Success: {result.success}")
        logger.warning(f"   Order ID: {result.order_id if result.success else 'N/A'}")
        if not result.success:
            logger.error(f"   Error message: {result.error_message}")

        return result
    
    def _handle_price_update(self, price: Decimal):
        """Handle price updates from WebSocket"""
        logger.info(f"Price update received: ${price}")
        self.current_price = price
        
        # Check for unit boundary crossing
        unit_event = self.unit_tracker.calculate_unit_change(price)
        
        if unit_event:
            logger.info(f"🎯 UNIT EVENT DETECTED - Creating task to handle unit change")
            asyncio.create_task(self._handle_unit_change(unit_event))
        else:
            logger.info(f"No unit change at price ${price}")
    
    async def _handle_unit_change(self, event: UnitChangeEvent):
        """Handle unit boundary crossing - Trail ONLY in the correct direction"""
        logger.warning(f"⚡ UNIT CROSSED! Unit {self.unit_tracker.current_unit} | Dir: {event.direction} | Phase: {event.phase}")

        current_unit = self.unit_tracker.current_unit
        previous_unit = event.previous_unit if hasattr(event, 'previous_unit') else current_unit - (1 if event.direction == 'up' else -1)

        # Count current orders
        stop_count = len(self.unit_tracker.trailing_stop)
        buy_count = len(self.unit_tracker.trailing_buy)

        # Log unit prices for debugging
        if current_unit in self.position_map:
            current_price = self.position_map[current_unit].price
            logger.info(f"📍 Current unit {current_unit} price: ${current_price:.4f}")

        # CRITICAL: Only trail in the correct direction!
        if event.direction == 'up':
            logger.info(f"📈 Price moved UP from unit {previous_unit} to {current_unit}")

            # ONLY trail STOPS upward if we have stops
            if stop_count > 0:
                logger.info(f"📈 TRAILING STOPS UP - Adding stop at {current_unit - 1}")
                await self._trail_stops_up()
            else:
                logger.info(f"📈 Price up but no stops to trail (have {buy_count} buys)")

        else:  # direction == 'down'
            logger.info(f"📉 Price moved DOWN from unit {previous_unit} to {current_unit}")

            # ONLY trail BUYS downward if we have buys
            if buy_count > 0:
                logger.info(f"📉 TRAILING BUYS DOWN - Adding buy at {current_unit + 1}")
                await self._trail_buys_down()
            else:
                logger.info(f"📉 Price down but no buys to trail (have {stop_count} stops)")

        # Log final state
        logger.info(f"Window state: Stops={sorted(self.unit_tracker.trailing_stop, reverse=True)}, Buys={sorted(self.unit_tracker.trailing_buy)}")

    async def _cancel_invalid_orders(self):
        """Cancel any invalid orders (triggered stops, stops above price, etc)"""
        try:
            # Get all open orders
            open_orders = self.sdk_client.get_open_orders(self.symbol)
            current_price = self.current_price

            for order in open_orders:
                order_id = order.get('oid')
                order_type = order.get('orderType', '')
                trigger_px = order.get('triggerPx')
                is_buy = order.get('side') == 'B'
                order_size = order.get('sz')

                # Check if it's a triggered stop order - EXECUTE IMMEDIATELY WITH MARKET ORDER
                if 'trigger' in order_type and order.get('triggered'):
                    logger.warning(f"⚠️ Found triggered-but-unfilled stop {order_id}")

                    # Cancel the stuck order
                    await self._cancel_order_by_id(order_id)

                    # Place immediate market order to close position
                    if not is_buy:  # Stop loss sell
                        logger.warning(f"🚨 EMERGENCY: Placing market SELL for {order_size} {self.symbol}")
                        result = await self._place_market_order("sell", Decimal(str(order_size)))
                        if result.success:
                            logger.warning(f"✅ Emergency market sell executed @ ${result.average_price}")
                    else:  # Stop buy
                        logger.warning(f"🚨 EMERGENCY: Placing market BUY for {order_size} {self.symbol}")
                        result = await self._place_market_order("buy", Decimal(str(order_size)))
                        if result.success:
                            logger.warning(f"✅ Emergency market buy executed @ ${result.average_price}")
                    continue

                # Cancel stop sells that are above current price (invalid)
                if not is_buy and trigger_px and Decimal(str(trigger_px)) > current_price:
                    logger.warning(f"🚫 Cancelling stop sell at ${trigger_px} (above current ${current_price})")
                    await self._cancel_order_by_id(order_id)
                    continue

                # Cancel stop buys that are below current price (invalid)
                if is_buy and trigger_px and Decimal(str(trigger_px)) < current_price:
                    logger.warning(f"🚫 Cancelling stop buy at ${trigger_px} (below current ${current_price})")
                    await self._cancel_order_by_id(order_id)
                    continue

        except Exception as e:
            logger.error(f"Error cancelling invalid orders: {e}")

    async def _cancel_order_by_id(self, order_id: str):
        """Cancel an order by its ID"""
        try:
            result = self.sdk_client.cancel_order(self.symbol, order_id)
            if result:
                # Clean up tracking
                if order_id in self.order_id_to_unit:
                    unit = self.order_id_to_unit[order_id]
                    del self.order_id_to_unit[order_id]

                    # Remove from tracking lists
                    if unit in self.unit_tracker.trailing_stop:
                        self.unit_tracker.remove_trailing_stop(unit)
                    if unit in self.unit_tracker.trailing_buy:
                        self.unit_tracker.remove_trailing_buy(unit)

                    logger.info(f"Cleaned up tracking for cancelled order at unit {unit}")
            return result
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def _trail_stops_up(self):
        """Trail stop losses UP when price rises - ONLY called when we have stops"""
        current_unit = self.unit_tracker.current_unit

        # Check if we already have a stop at current_unit - 1
        target_unit = current_unit - 1
        if target_unit not in self.unit_tracker.trailing_stop:
            logger.info(f"📈 Adding new stop at unit {target_unit}")

            # Place the new stop
            order_id = await self._place_stop_loss_order(target_unit)
            if order_id:
                self.unit_tracker.add_trailing_stop(target_unit)

                # If we now have 5 stops, remove the furthest one
                if len(self.unit_tracker.trailing_stop) > 4:
                    furthest = min(self.unit_tracker.trailing_stop)
                    logger.info(f"🗑️ Removing furthest stop at unit {furthest}")
                    await self._cancel_order(furthest)
                    self.unit_tracker.remove_trailing_stop(furthest)
        else:
            logger.info(f"✓ Stop already exists at unit {target_unit}")

    async def _trail_buys_down(self):
        """Trail buy orders DOWN when price falls - ONLY called when we have buys"""
        current_unit = self.unit_tracker.current_unit

        # Check if we already have a buy at current_unit + 1
        target_unit = current_unit + 1
        if target_unit not in self.unit_tracker.trailing_buy:
            logger.info(f"📉 Adding new buy at unit {target_unit}")

            # Place the new buy
            order_id = await self._place_stop_buy_order(target_unit)
            if order_id:
                self.unit_tracker.add_trailing_buy(target_unit)

                # If we now have 5 buys, remove the furthest one
                if len(self.unit_tracker.trailing_buy) > 4:
                    furthest = max(self.unit_tracker.trailing_buy)
                    logger.info(f"🗑️ Removing furthest buy at unit {furthest}")
                    await self._cancel_order(furthest)
                    self.unit_tracker.remove_trailing_buy(furthest)
        else:
            logger.info(f"✓ Buy already exists at unit {target_unit}")

    async def _validate_and_repair_window(self):
        """Validate and repair the window - ONLY fill gaps, don't trail"""
        # This function should ONLY run after order fills to ensure we have 4 orders
        # It should NOT reposition orders based on current price

        stop_count = len(self.unit_tracker.trailing_stop)
        buy_count = len(self.unit_tracker.trailing_buy)
        total_orders = stop_count + buy_count

        logger.info(f"🔧 WINDOW VALIDATION - Stops: {stop_count}, Buys: {buy_count}, Total: {total_orders}")

        # If we already have 4 orders, we're good
        if total_orders == 4:
            logger.info(f"✅ Window already has 4 orders, no repair needed")
            return

        # If we have MORE than 4, something is wrong
        if total_orders > 4:
            logger.error(f"⚠️ ERROR: Have {total_orders} orders instead of 4!")
            return

        # Only log the issue - do NOT try to "repair" by adding orders
        # The only time we should add orders is:
        # 1. During initialization
        # 2. After an order fill (replacement)
        # 3. When trailing UP (stops) or DOWN (buys)
        if total_orders < 4:
            logger.warning(f"⚠️ Window has {total_orders} orders instead of 4 - Stops: {self.unit_tracker.trailing_stop}, Buys: {self.unit_tracker.trailing_buy}")

    async def _cancel_orders_outside_window(self, desired_stops: List[int], desired_buys: List[int]):
        """Cancel any orders that shouldn't be in the window"""

        current_unit = self.unit_tracker.current_unit

        # Cancel ALL stops that aren't in desired list
        stops_to_cancel = [u for u in self.unit_tracker.trailing_stop if u not in desired_stops]
        if stops_to_cancel:
            logger.warning(f"🚫 CANCELLING STOPS outside window: {stops_to_cancel}")
            for unit in stops_to_cancel:
                if unit in self.position_map and self.position_map[unit].is_active:
                    success = await self._cancel_order(unit)
                    if success:
                        self.unit_tracker.remove_trailing_stop(unit)
                else:
                    # Remove from list even if not in position_map
                    self.unit_tracker.remove_trailing_stop(unit)
                    logger.warning(f"   Removed stale stop at unit {unit} from tracking")

        # CRITICAL: Handle buy cancellations carefully
        buys_to_cancel = []
        for unit in self.unit_tracker.trailing_buy:
            if unit not in desired_buys:
                # NEVER cancel the buy at current_unit + 1
                if unit == current_unit + 1:
                    logger.warning(f"🛡️ PROTECTING buy at unit {unit} (current+1) - will NOT cancel")
                    continue

                # Check if we would have too many buys
                if len(self.unit_tracker.trailing_buy) > 4:
                    # Only cancel furthest buy when we have 5+
                    buys_to_cancel.append(unit)
                else:
                    logger.info(f"   Keeping buy at unit {unit} (only have {len(self.unit_tracker.trailing_buy)} buys)")

        # Sort buys to cancel by distance from current price (furthest first)
        buys_to_cancel.sort(reverse=True)  # Highest unit numbers first (furthest from price)

        if buys_to_cancel:
            logger.warning(f"🚫 CANCELLING BUYS outside window: {buys_to_cancel}")
            for unit in buys_to_cancel:
                # One more check - never cancel current+1
                if unit == current_unit + 1:
                    logger.error(f"⚠️ BLOCKED: Attempted to cancel protected buy at unit {unit}")
                    continue

                if unit in self.position_map and self.position_map[unit].is_active:
                    success = await self._cancel_order(unit)
                    if success:
                        self.unit_tracker.remove_trailing_buy(unit)
                        logger.info(f"   Cancelled buy at unit {unit}")
                else:
                    # Remove from list even if not in position_map
                    self.unit_tracker.remove_trailing_buy(unit)
                    logger.warning(f"   Removed stale buy at unit {unit} from tracking")

    async def _place_missing_orders(self, desired_stops: List[int], desired_buys: List[int]):
        """Place any orders that are missing from the window"""

        # Place missing stops
        stops_placed = 0
        for unit in desired_stops:
            if unit not in self.unit_tracker.trailing_stop:
                # Ensure unit exists in position map
                if unit not in self.position_map:
                    add_unit_level(self.position_state, self.position_map, unit)

                # Get the actual price for this unit
                unit_price = self.position_map[unit].price
                logger.warning(f"📌 Placing missing STOP at unit {unit} (price: ${unit_price:.2f})")

                order_id = await self._place_stop_loss_order(unit)
                if order_id:
                    self.unit_tracker.add_trailing_stop(unit)
                    stops_placed += 1
                    logger.warning(f"✅ Placed stop at unit {unit} @ ${unit_price:.2f}")
                else:
                    logger.error(f"❌ Failed to place stop at unit {unit}")

        # Place missing buys
        buys_placed = 0
        for unit in desired_buys:
            if unit not in self.unit_tracker.trailing_buy:
                # Ensure unit exists in position map
                if unit not in self.position_map:
                    add_unit_level(self.position_state, self.position_map, unit)

                # Get the actual price for this unit
                unit_price = self.position_map[unit].price
                logger.warning(f"📌 Placing missing BUY at unit {unit} (price: ${unit_price:.2f})")

                order_id = await self._place_stop_buy_order(unit)
                if order_id:
                    self.unit_tracker.add_trailing_buy(unit)
                    buys_placed += 1
                    logger.warning(f"✅ Placed buy at unit {unit} @ ${unit_price:.2f}")
                else:
                    logger.error(f"❌ Failed to place buy at unit {unit}")

        if stops_placed > 0 or buys_placed > 0:
            logger.warning(f"📊 WINDOW REPAIR: Placed {stops_placed} stops, {buys_placed} buys")


    async def _cancel_order(self, unit: int) -> bool:
        """Cancel an order at a specific unit"""
        config = self.position_map[unit]
        if config.order_id:
            order_id = config.order_id
            order_type = config.order_type.value if config.order_type else "unknown"

            logger.warning(f"🚫 CANCELLING {order_type} at unit {unit} (ID: {order_id})")

            # Cancel via SDK
            success = self.sdk_client.cancel_order(self.symbol, order_id)
            if success:
                config.mark_cancelled()
                # Clean up order ID mapping
                if order_id in self.order_id_to_unit:
                    del self.order_id_to_unit[order_id]
                logger.warning(f"✅ CANCELLED {order_type} at unit {unit}")
                return True
            else:
                logger.error(f"❌ FAILED to cancel {order_type} at unit {unit}")
                return False
        return False
    
    async def handle_order_fill(self, order_id: str, filled_price: Decimal, filled_size: Decimal):
        """Handle order fill notification with O(1) lookup via order ID mapping"""
        logger.warning(f"🔔 FILL RECEIVED - Order ID: {order_id}, Price: ${filled_price:.2f}, Size: {filled_size}")

        # Filter out initial position order
        if hasattr(self, 'initial_order_id') and order_id == self.initial_order_id:
            logger.info(f"Ignoring initial position order fill (ID: {order_id})")
            return

        # FAST LOOKUP: Use order_id_to_unit mapping
        if order_id not in self.order_id_to_unit:
            logger.warning(f"⚠️ Order {order_id} not found in order_id_to_unit mapping!")
            logger.warning(f"📋 Current mapping: {self.order_id_to_unit}")

            # Fallback to old method for safety
            filled_unit = None
            for unit, config in self.position_map.items():
                if config.order_id == order_id:
                    filled_unit = unit
                    break

            if filled_unit is None:
                logger.error(f"❌ Could not match order {order_id} to any unit in position_map!")
                return
        else:
            filled_unit = self.order_id_to_unit[order_id]
            logger.info(f"✅ Fast lookup: Order {order_id} maps to unit {filled_unit}")

        # Get the config and mark as filled
        config = self.position_map[filled_unit]
        filled_order_type = config.order_type
        config.mark_filled(filled_price, filled_size)

        # Clean up order ID mapping
        if order_id in self.order_id_to_unit:
            del self.order_id_to_unit[order_id]
        
        logger.info(f"Order filled at unit {filled_unit}: {filled_order_type.value} {filled_size:.6f} @ ${filled_price:.2f}")

        # Update lists based on fill type
        if filled_order_type == OrderType.STOP_LOSS_SELL:
            # Stop-loss executed - remove from trailing_stop list
            self.unit_tracker.remove_trailing_stop(filled_unit)

            # Track realized PnL (sell price - entry price)
            self.unit_tracker.track_realized_pnl(
                sell_price=filled_price,
                buy_price=self.position_state.entry_price,
                size=filled_size
            )

            # Check if we still have a position after this fill
            positions = self.sdk_client.get_positions()
            remaining_position = 0
            if self.symbol in positions:
                remaining_position = positions[self.symbol].size

            # IMPORTANT: After a stop loss, place a buy order for re-entry
            replacement_unit = filled_unit + 1
            logger.warning(f"🔄 Stop loss filled at unit {filled_unit}, placing BUY at unit {replacement_unit}")
            logger.warning(f"📊 Remaining position after fill: {remaining_position} {self.symbol}")

            # Ensure unit exists in position map
            if replacement_unit not in self.position_map:
                from strategy.position_map import add_unit_level
                add_unit_level(self.position_state, self.position_map, replacement_unit)

            # Place the buy order
            order_id = await self._place_stop_buy_order(replacement_unit)
            if order_id:
                self.unit_tracker.add_trailing_buy(replacement_unit)
                logger.warning(f"✅ Placed stop BUY at unit {replacement_unit} for re-entry")

            # If we're completely out of position, switch to buy-only mode
            if remaining_position == 0:
                logger.warning(f"🚨 POSITION CLOSED - Switching to buy-only mode")
                # Clear all stop orders
                self.unit_tracker.trailing_stop.clear()
                # The validation will handle setting up buy orders

        elif filled_order_type == OrderType.STOP_BUY:
            # Buy executed - remove from trailing_buy list
            self.unit_tracker.remove_trailing_buy(filled_unit)

            # Check our position after the buy
            positions = self.sdk_client.get_positions()
            current_position = 0
            if self.symbol in positions:
                current_position = positions[self.symbol].size

            logger.warning(f"📊 Position after buy fill: {current_position} {self.symbol}")

            # IMPORTANT: After a buy fill, place a stop loss for protection
            replacement_unit = filled_unit - 1
            logger.warning(f"🔄 Stop buy filled at unit {filled_unit}, placing STOP at unit {replacement_unit}")

            # Ensure unit exists in position map
            if replacement_unit not in self.position_map:
                from strategy.position_map import add_unit_level
                add_unit_level(self.position_state, self.position_map, replacement_unit)

            # Place the stop order
            order_id = await self._place_stop_loss_order(replacement_unit)
            if order_id:
                self.unit_tracker.add_trailing_stop(replacement_unit)
                logger.warning(f"✅ Placed stop LOSS at unit {replacement_unit} for protection")

            # If this was our first entry (we just got a position), we may need more stops
            if current_position > 0 and len(self.unit_tracker.trailing_stop) < 3:
                logger.warning(f"🔧 New position established - will add more stops in validation")

        # CRITICAL: After placing replacement orders, validate and repair the window
        # This ensures we always have exactly 4 orders properly positioned
        logger.info(f"🔧 Validating window after fill at unit {filled_unit}")
        await self._validate_and_repair_window()

        # Log final state
        logger.info(f"Lists after fill: Stop={self.unit_tracker.trailing_stop}, Buy={self.unit_tracker.trailing_buy}")

        # Verify we have exactly 4 orders
        total_orders = len(self.unit_tracker.trailing_stop) + len(self.unit_tracker.trailing_buy)
        if total_orders != 4:
            logger.error(f"⚠️ ERROR: After fill, have {total_orders} orders instead of 4!")
            logger.error(f"   Stops: {self.unit_tracker.trailing_stop}")
            logger.error(f"   Buys: {self.unit_tracker.trailing_buy}")
    
    async def run(self):
        """Main trading loop"""
        self.is_running = True
        logger.info("Starting HyperTrader main loop")

        try:
            # Start WebSocket listening
            listen_task = asyncio.create_task(self.ws_client.listen())

            # Main loop
            while self.is_running:
                # Monitor position and orders
                window_state = self.unit_tracker.get_window_state()
                active_orders = get_active_orders(self.position_map)

                # Log detailed order status every 30 seconds
                if not hasattr(self, '_last_detail_log'):
                    self._last_detail_log = 0
                    self._last_validation = 0

                self._last_detail_log += 1
                self._last_validation += 1

                if self._last_detail_log >= 3:  # Every 30 seconds (10s * 3)
                    self._log_order_summary(active_orders)
                    self._last_detail_log = 0
                else:
                    logger.info(f"Status - Phase: {window_state['phase']}, Active orders: {len(active_orders)}, Current unit: {window_state['current_unit']}")

                # Periodically clean up invalid orders (every 20 seconds)
                if self._last_validation >= 2:  # Every 20 seconds (10s * 2)
                    logger.info("🔍 Periodic cleanup of invalid orders")
                    await self._cancel_invalid_orders()  # Clean up bad orders
                    # Do NOT call validate_and_repair - it was adding orders in wrong places!
                    self._last_validation = 0

                # Sleep for monitoring interval
                await asyncio.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.is_running = False
            await self.shutdown()
    
    def _log_order_summary(self, active_orders: Dict[int, PositionConfig]):
        """Log summary of all active orders using trailing lists"""
        # Use the actual trailing lists for accurate counts
        stop_losses = []
        for unit in self.unit_tracker.trailing_stop:
            if unit in self.position_map:
                stop_losses.append(f"Unit {unit}: ${self.position_map[unit].price:.2f}")
        
        stop_buys = []
        for unit in self.unit_tracker.trailing_buy:
            if unit in self.position_map:
                stop_buys.append(f"Unit {unit}: ${self.position_map[unit].price:.2f}")
        
        
        # Log using actual list counts
        logger.info(f"📊 ORDERS - Stop sells: {len(self.unit_tracker.trailing_stop)}, Stop buys: {len(self.unit_tracker.trailing_buy)}")
        if stop_losses:
            logger.info(f"   Stop-losses: {', '.join(stop_losses[:4])}")
        if stop_buys:
            logger.info(f"   Stop buys: {', '.join(stop_buys[:4])}")
        

    async def shutdown(self):
        """Clean shutdown of all components"""
        logger.info("Shutting down HyperTrader...")
        
        # Log final state
        if self.current_price:
            logger.info(f"Final price: ${self.current_price:.2f}")
        
        # Disconnect WebSocket
        if self.ws_client:
            await self.ws_client.disconnect()
        
        logger.info("HyperTrader shutdown complete")


async def main():
    """Main entry point"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="HyperTrader - Sliding Window Strategy Bot")
    parser.add_argument("--symbol", required=True, help="Trading symbol (e.g., ETH, BTC)")
    parser.add_argument("--wallet", choices=["long"], default="long", help="Wallet type (only 'long' supported)")
    parser.add_argument("--testnet", action="store_true", help="Use testnet")
    parser.add_argument("--unit-size", type=float, required=True, help="Unit size in USD")
    parser.add_argument("--position-size", type=float, required=True, help="Initial position size in USD")
    parser.add_argument("--leverage", type=int, required=True, help="Leverage to use (e.g., 10, 25)")
    
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(f"logs/hypertrader_{args.wallet}_{datetime.now():%Y%m%d_%H%M%S}.log", level="DEBUG")
    
    # Create and run trader
    trader = HyperTrader(
        symbol=args.symbol,
        wallet_type=args.wallet,
        use_testnet=args.testnet
    )
    
    trader.unit_size_usd = Decimal(str(args.unit_size))
    trader.initial_position_size = Decimal(str(args.position_size))
    trader.leverage = args.leverage
    
    # Initialize
    if await trader.initialize():
        # Run main loop
        await trader.run()
    else:
        logger.error("Failed to initialize trader")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())