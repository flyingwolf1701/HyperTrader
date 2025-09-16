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
from dotenv import load_dotenv

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
from core.websocket_client import HyperliquidWebSocketClient


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
        self.ws_client: Optional[HyperliquidWebSocketClient] = None
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
        
        logger.info(f"Initializing HyperTrader for {symbol} - {wallet_type} wallet")
    
    async def initialize(self):
        """Initialize all components and connections"""
        try:
            # Load environment variables
            load_dotenv()
            
            # Initialize SDK client (determines wallet based on type)
            use_sub_wallet = (self.wallet_type == "hedge")
            self.sdk_client = HyperliquidClient(
                use_testnet=self.use_testnet,
                use_sub_wallet=use_sub_wallet
            )
            logger.info(f"SDK client initialized for {self.wallet_type} wallet")
            
            # Get user address from SDK for order tracking
            user_address = self.sdk_client.get_user_address()
            
            # Initialize WebSocket client with user address
            self.ws_client = HyperliquidWebSocketClient(
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
        # Check if we have an existing position
        positions = self.sdk_client.get_positions()
        
        if self.symbol in positions:
            # Load existing position
            position = positions[self.symbol]
            entry_price = position.entry_price
            asset_size = position.size
            logger.info(f"Loaded existing position: {asset_size} {self.symbol} @ ${entry_price:.2f}")
        else:
            # Create new position
            estimated_price = self.current_price
            estimated_size = self.initial_position_size / estimated_price
            logger.info(f"Creating new position: ~{estimated_size:.6f} {self.symbol} @ ~${estimated_price:.2f}")
            
            # Place initial market buy order (for long wallet)
            if self.wallet_type == "long":
                result = await self._place_market_order("buy", estimated_size)
                if not result.success:
                    raise Exception(f"Failed to create initial position: {result.error_message}")
                
                # Track initial order ID to filter from fill matching
                self.initial_order_id = result.order_id
                logger.info(f"Initial position order ID: {self.initial_order_id}")
                
                # CRITICAL: Wait for position to be fully established
                logger.info("⏳ Waiting for initial position to be fully established...")
                
                # Poll for position with timeout
                max_attempts = 10
                for attempt in range(max_attempts):
                    await asyncio.sleep(1)
                    positions = self.sdk_client.get_positions()
                    if self.symbol in positions:
                        logger.info(f"Position found after {attempt + 1} second(s)")
                        break
                else:
                    raise Exception(f"Position not found after {max_attempts} seconds")
                
                position = positions[self.symbol]
                entry_price = position.entry_price  # Use ACTUAL average fill price
                asset_size = position.size  # Use ACTUAL position size
                logger.info(f"✅ Position established: {asset_size:.6f} {self.symbol} @ ${entry_price:.2f} (actual fill price)")
        
        # Initialize position map with ACTUAL entry price
        self.position_state, self.position_map = calculate_initial_position_map(
            entry_price=entry_price,
            unit_size_usd=self.unit_size_usd,
            asset_size=asset_size,
            position_value_usd=asset_size * entry_price,  # Use actual position value
            unit_range=20  # Pre-calculate more units for sliding window
        )
        
        # Initialize unit tracker with sliding window
        self.unit_tracker = UnitTracker(
            position_state=self.position_state,
            position_map=self.position_map
        )
        
        # Place initial sliding window orders
        await self._place_window_orders()
        
        logger.info(f"Position initialized with sliding window: {self.unit_tracker.get_window_state()}")
    
    async def _place_window_orders(self):
        """Place initial stop loss orders using list-based tracking"""
        # Initialize with 4 stop-losses (already set in unit_tracker init, but ensure it's correct)
        if not self.unit_tracker.trailing_stop:
            self.unit_tracker.trailing_stop = [-4, -3, -2, -1]
            self.unit_tracker.trailing_buy = []
        
        logger.warning(f"📋 INITIAL WINDOW STATE:")
        logger.warning(f"   trailing_stop: {self.unit_tracker.trailing_stop}")
        logger.warning(f"   trailing_buy: {self.unit_tracker.trailing_buy}")
        
        # Place stop losses at designated units
        order_ids = []
        for unit in self.unit_tracker.trailing_stop:
            if unit in self.position_map and not self.position_map[unit].is_active:
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
        price = config.price

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
                reduce_only=False
            )
            
            if result.success:
                config.set_active_order(result.order_id, OrderType.STOP_BUY)
                logger.warning(f"✅ STOP BUY SUCCESSFULLY PLACED at unit {unit} (triggers @ ${price:.2f})")
                logger.warning(f"📝 ORDER ID TRACKING: Stop buy at unit {unit} = {result.order_id}")
                return result.order_id
            else:
                logger.error(f"❌ STOP BUY FAILED at unit {unit}: {result.error_message}")
                return None
        else:
            # Price is below market - use regular stop buy
            logger.info(f"📉 Price ${price:.2f} <= Market ${current_market_price:.2f} - Using regular stop buy")
            result = await self._place_stop_order(unit, "buy")

            if result:
                logger.warning(f"✅ STOP BUY SUCCESSFULLY PLACED at unit {unit}")
            else:
                logger.error(f"❌ STOP BUY FAILED at unit {unit}")
                
            return result
    
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
        trigger_price = config.price
        
        # Stop losses are always sells that reduce the long position
        size = self.position_state.long_fragment_asset
        
        # Place stop order via SDK
        result = await self._sdk_place_stop_order("sell", trigger_price, size)
        
        if result.success:
            # Update position map
            config.set_active_order(result.order_id, OrderType.STOP_LOSS_SELL)
            logger.info(f"Placed STOP LOSS at unit {unit}: {size:.6f} {self.symbol} triggers @ ${trigger_price:.2f}")
            logger.warning(f"📝 ORDER ID TRACKING: Stop-loss at unit {unit} = {result.order_id}")
            return result.order_id
        else:
            logger.error(f"Failed to place stop loss at unit {unit}: {result.error_message}")
            return None
    
    
    async def _sdk_place_stop_order(self, side: str, trigger_price: Decimal, size: Decimal) -> OrderResult:
        """Place stop order via SDK"""
        is_buy = (side.lower() == "buy")
        return self.sdk_client.place_stop_order(
            symbol=self.symbol,
            is_buy=is_buy,
            size=size,
            trigger_price=trigger_price,
            reduce_only=(not is_buy)  # Only sells reduce position, buys open position
        )
    
    async def _place_market_order(self, side: str, size: Decimal) -> OrderResult:
        """Place market order via SDK"""
        is_buy = (side.lower() == "buy")
        
        # Calculate USD amount for the order
        current_price = await self._get_current_price()
        usd_amount = size * current_price
        
        return self.sdk_client.open_position(
            symbol=self.symbol,
            usd_amount=usd_amount,
            is_long=is_buy,
            leverage=self.leverage,
            slippage=0.01
        )
    
    def _handle_price_update(self, price: Decimal):
        """Handle price updates from WebSocket"""
        logger.debug(f"Price update received: ${price}")
        self.current_price = price
        
        # Check for unit boundary crossing
        unit_event = self.unit_tracker.calculate_unit_change(price)
        
        if unit_event:
            logger.info(f"🎯 UNIT EVENT DETECTED - Creating task to handle unit change")
            asyncio.create_task(self._handle_unit_change(unit_event))
        else:
            logger.debug(f"No unit change at price ${price}")
    
    async def _handle_unit_change(self, event: UnitChangeEvent):
        """Handle unit boundary crossing - Simple data_flow.md approach"""
        logger.warning(f"⚡ UNIT CROSSED! Unit {self.unit_tracker.current_unit} | Dir: {event.direction} | Phase: {event.phase}")

        current_unit = self.unit_tracker.current_unit

        if event.direction == 'up':
            # Price went UP - as per data_flow.md step 7
            # Place new stop at current_unit - 1
            new_stop_unit = current_unit - 1

            # Ensure unit exists in position map
            if new_stop_unit not in self.position_map:
                add_unit_level(self.position_state, self.position_map, new_stop_unit)

            # Place new stop if not already there
            if new_stop_unit not in self.unit_tracker.trailing_stop:
                order_id = await self._place_stop_loss_order(new_stop_unit)
                if order_id:
                    self.unit_tracker.add_trailing_stop(new_stop_unit)
                    logger.info(f"✅ Placed new stop at unit {new_stop_unit}")

            # Cancel the oldest (furthest) stop if we have more than 4
            if len(self.unit_tracker.trailing_stop) > 4:
                # Sort to find the lowest unit (furthest below current price)
                sorted_stops = sorted(self.unit_tracker.trailing_stop)
                oldest_stop = sorted_stops[0]

                # Cancel and remove
                if oldest_stop in self.position_map and self.position_map[oldest_stop].is_active:
                    success = await self._cancel_order(oldest_stop)
                    if success:
                        self.unit_tracker.remove_trailing_stop(oldest_stop)
                        logger.info(f"🚫 Cancelled old stop at unit {oldest_stop}")

        elif event.direction == 'down':
            # Price went DOWN - as per data_flow.md step 10
            # Place new buy at current_unit + 1
            new_buy_unit = current_unit + 1

            # Ensure unit exists in position map
            if new_buy_unit not in self.position_map:
                add_unit_level(self.position_state, self.position_map, new_buy_unit)

            # Place new buy if not already there
            if new_buy_unit not in self.unit_tracker.trailing_buy:
                order_id = await self._place_stop_buy_order(new_buy_unit)
                if order_id:
                    self.unit_tracker.add_trailing_buy(new_buy_unit)
                    logger.info(f"✅ Placed new buy at unit {new_buy_unit}")

            # Cancel the oldest (furthest) buy if we have more than 4
            if len(self.unit_tracker.trailing_buy) > 4:
                # Sort to find the highest unit (furthest above current price)
                sorted_buys = sorted(self.unit_tracker.trailing_buy, reverse=True)
                oldest_buy = sorted_buys[0]

                # Cancel and remove
                if oldest_buy in self.position_map and self.position_map[oldest_buy].is_active:
                    success = await self._cancel_order(oldest_buy)
                    if success:
                        self.unit_tracker.remove_trailing_buy(oldest_buy)
                        logger.info(f"🚫 Cancelled old buy at unit {oldest_buy}")

        # Log current state
        logger.info(f"Window state: Stops={self.unit_tracker.trailing_stop}, Buys={self.unit_tracker.trailing_buy}")

    
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
                logger.warning(f"✅ CANCELLED {order_type} at unit {unit}")
                return True
            else:
                logger.error(f"❌ FAILED to cancel {order_type} at unit {unit}")
                return False
        return False
    
    async def handle_order_fill(self, order_id: str, filled_price: Decimal, filled_size: Decimal):
        """Handle order fill notification with proper list updates"""
        logger.warning(f"🔔 FILL RECEIVED - Order ID: {order_id}, Price: ${filled_price:.2f}, Size: {filled_size}")
        
        # Filter out initial position order
        if hasattr(self, 'initial_order_id') and order_id == self.initial_order_id:
            logger.info(f"Ignoring initial position order fill (ID: {order_id})")
            return
        
        # Log current order IDs in position map for debugging
        active_orders = {unit: config.order_id for unit, config in self.position_map.items() if config.order_id}
        logger.warning(f"📋 Active orders in position_map: {active_orders}")
        logger.warning(f"📋 Trying to match incoming order ID: {order_id}")
        
        # Find the unit that was filled
        filled_unit = None
        filled_order_type = None
        
        for unit, config in self.position_map.items():
            if config.order_id == order_id:
                filled_unit = unit
                filled_order_type = config.order_type
                config.mark_filled(filled_price, filled_size)
                logger.info(f"✅ Matched order {order_id} to unit {filled_unit}")
                break
        
        if filled_unit is not None:
            logger.info(f"Order filled at unit {filled_unit}: {filled_order_type.value} {filled_size:.6f} @ ${filled_price:.2f}")

            # NEW LIST-BASED TRACKING: Update lists based on fill type
            if filled_order_type == OrderType.STOP_LOSS_SELL:
                # Stop-loss executed - remove from trailing_stop list
                self.unit_tracker.remove_trailing_stop(filled_unit)

                # Track realized PnL (sell price - entry price)
                self.unit_tracker.track_realized_pnl(
                    sell_price=filled_price,
                    buy_price=self.position_state.entry_price,
                    size=filled_size
                )
                
                # Add replacement buy at filled_unit + 1
                replacement_unit = filled_unit + 1
                
                # Ensure unit exists in position map
                if replacement_unit not in self.position_map:
                    add_unit_level(self.position_state, self.position_map, replacement_unit)
                
                # Add to trailing_buy list and place order
                if self.unit_tracker.add_trailing_buy(replacement_unit):
                    order_id = await self._place_stop_buy_order(replacement_unit)
                    if order_id:
                        logger.info(f"✅ Stop filled at {filled_unit}, placed stop buy at {replacement_unit}")
                    else:
                        logger.error(f"❌ Failed to place replacement stop buy at {replacement_unit}")

            elif filled_order_type == OrderType.STOP_BUY:
                # Buy executed - remove from trailing_buy list
                self.unit_tracker.remove_trailing_buy(filled_unit)
                
                # Add replacement stop at filled_unit - 1
                replacement_unit = filled_unit - 1
                
                # Ensure unit exists in position map
                if replacement_unit not in self.position_map:
                    add_unit_level(self.position_state, self.position_map, replacement_unit)
                
                # Add to trailing_stop list and place order
                if self.unit_tracker.add_trailing_stop(replacement_unit):
                    order_id = await self._place_stop_loss_order(replacement_unit)
                    if order_id:
                        logger.info(f"✅ Buy filled at {filled_unit}, placed stop at {replacement_unit}")
                    else:
                        logger.error(f"❌ Failed to place replacement stop at {replacement_unit}")
            
            # Removed handle_order_execution call - not needed with list-based tracking
            
            # Log current list state
            logger.info(f"Lists after fill: Stop={self.unit_tracker.trailing_stop}, Buy={self.unit_tracker.trailing_buy}")
            
            # Log window state after fill
            window_state = self.unit_tracker.get_window_state()
            logger.debug(f"Window state after fill: {window_state}")
        else:
            logger.warning(f"⚠️ Could not match order {order_id} to any unit in position_map!")
    
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
                self._last_detail_log += 1

                if self._last_detail_log >= 3:  # Every 30 seconds (10s * 3)
                    self._log_order_summary(active_orders)
                    self._last_detail_log = 0
                else:
                    logger.debug(f"Status - Phase: {window_state['phase']}, Active orders: {len(active_orders)}, Current unit: {window_state['current_unit']}")

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