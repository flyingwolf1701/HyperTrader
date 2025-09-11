"""
HyperTrader Main Entry Point - Sliding Window Strategy v9.2.6
Integrates position map, unit tracker, SDK, and WebSocket for automated trading
"""

import asyncio
import sys
import os
from decimal import Decimal
from typing import Optional, Dict
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

# Add src directory to path for absolute imports
src_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, src_dir)

# Import new strategy components
from strategy.data_models import (
    OrderType, Phase, ExecutionStatus, PositionState, 
    WindowState, PositionConfig, UnitChangeEvent, OrderFillEvent
)
from strategy.strategy_engine import LongWalletStrategy
from strategy.order_manager import OrderManager
from strategy.position_tracker import PositionTracker
from strategy.position_map import (
    calculate_initial_position_map,
    add_unit_level,
    get_active_orders,
    get_window_orders
)
from strategy.unit_tracker import UnitTracker  # For backward compatibility
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
                unit_size_usd=self.unit_size_usd,
                unit_tracker=self.unit_tracker,
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
            position_map=self.position_map,
            wallet_type=self.wallet_type
        )
        
        # Place initial sliding window orders
        await self._place_window_orders()
        
        logger.info(f"Position initialized with sliding window: {self.unit_tracker.get_window_state()}")
    
    async def _place_window_orders(self):
        """Place stop loss orders for the sliding window"""
        window_state = self.unit_tracker.get_window_state()
        
        # Place stop losses at negative units below current price
        # These protect the position by triggering when price drops
        for unit in window_state['sell_orders']:
            if unit in self.position_map and not self.position_map[unit].is_active:
                await self._place_stop_loss_order(unit)
        
        logger.info(f"Placed stop losses at units: {window_state['sell_orders']}")
    
    async def _place_limit_order(self, unit: int, side: str) -> Optional[str]:
        """Place a limit order at a specific unit"""
        config = self.position_map[unit]
        price = config.price
        
        # Determine size based on fragment type
        if side == "sell":
            size = self.position_state.long_fragment_asset
            order_type = OrderType.STOP_LOSS_SELL
        else:
            # Calculate size in asset terms from USD fragment
            size = self.position_state.long_fragment_usd / price
            order_type = OrderType.LIMIT_BUY
        
        # Place order via SDK
        result = await self._sdk_place_limit_order(side, price, size)
        
        if result.success:
            # Update position map
            config.set_active_order(result.order_id, order_type, in_window=True)
            logger.info(f"Placed {side} order at unit {unit}: {size:.6f} @ ${price:.2f}")
            return result.order_id
        else:
            logger.error(f"Failed to place {side} order at unit {unit}: {result.error_message}")
            return None
    
    async def _place_limit_buy_order(self, unit: int) -> Optional[str]:
        """Place a limit buy order at a specific unit"""
        return await self._place_limit_order(unit, "buy")
    
    async def _place_stop_loss_order(self, unit: int) -> Optional[str]:
        """Place a stop loss order at a specific unit"""
            
        config = self.position_map[unit]
        trigger_price = config.price
        
        # Stop losses are always sells that reduce the long position
        size = self.position_state.long_fragment_asset
        
        # Place stop order via SDK
        result = await self._sdk_place_stop_order("sell", trigger_price, size)
        
        if result.success:
            # Update position map
            config.set_active_order(result.order_id, OrderType.STOP_LOSS_SELL, "stop_loss_orders")
            logger.info(f"Placed STOP LOSS at unit {unit}: {size:.6f} {self.symbol} triggers @ ${trigger_price:.2f}")
            return result.order_id
        else:
            logger.error(f"Failed to place stop loss at unit {unit}: {result.error_message}")
            return None
    
    async def _sdk_place_limit_order(self, side: str, price: Decimal, size: Decimal) -> OrderResult:
        """Place limit order via SDK"""
        is_buy = (side.lower() == "buy")
        return self.sdk_client.place_limit_order(
            symbol=self.symbol,
            is_buy=is_buy,
            price=price,
            size=size,
            reduce_only=False,
            post_only=True  # Maker orders only to avoid fees
        )
    
    async def _sdk_place_stop_order(self, side: str, trigger_price: Decimal, size: Decimal) -> OrderResult:
        """Place stop loss order via SDK"""
        is_buy = (side.lower() == "buy")
        return self.sdk_client.place_stop_order(
            symbol=self.symbol,
            is_buy=is_buy,
            size=size,
            trigger_price=trigger_price,
            reduce_only=True  # Stop losses always reduce position
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
        self.current_price = price
        
        # Check for unit boundary crossing
        unit_event = self.unit_tracker.calculate_unit_change(price)
        
        if unit_event:
            asyncio.create_task(self._handle_unit_change(unit_event))
    
    async def _handle_unit_change(self, event: UnitChangeEvent):
        """Handle unit boundary crossing"""
        logger.info(f"Unit changed to {self.unit_tracker.current_unit} - Direction: {event.direction} - Phase: {event.phase}")
        
        # PROACTIVE STRATEGY: Place orders immediately on unit crossing
        current_unit = self.unit_tracker.current_unit
        
        if event.direction == 'down':
            # When price drops to a new unit, immediately place limit buy at current+1
            # This assumes the stop-loss at this level will/has triggered
            replacement_unit = current_unit + 1
            
            # Ensure unit exists in position map
            if replacement_unit not in self.position_map:
                add_unit_level(self.position_state, self.position_map, replacement_unit)
            
            # Check if we already have an active order at this unit
            if not self.position_map[replacement_unit].is_active:
                logger.warning(f"🚀 PROACTIVE: Price dropped to unit {current_unit}, placing limit buy at unit {replacement_unit}")
                
                # Place limit buy order immediately
                order_id = await self._place_limit_buy_order(replacement_unit)
                if order_id:
                    logger.info(f"✅ PROACTIVE limit buy placed at unit {replacement_unit}")
                else:
                    logger.error(f"❌ Failed to place PROACTIVE limit buy at unit {replacement_unit}")
            else:
                logger.debug(f"Already have active order at unit {replacement_unit}, skipping proactive placement")
                
        elif event.direction == 'up':
            # When price rises to a new unit, immediately place stop-loss at current-1
            # This assumes a limit buy at this level will/has filled
            replacement_unit = current_unit - 1
            
            # Ensure unit exists in position map
            if replacement_unit not in self.position_map:
                add_unit_level(self.position_state, self.position_map, replacement_unit)
            
            # Check if we already have an active order at this unit
            if not self.position_map[replacement_unit].is_active:
                logger.warning(f"🚀 PROACTIVE: Price rose to unit {current_unit}, placing stop-loss at unit {replacement_unit}")
                
                # Place stop-loss order immediately
                order_id = await self._place_stop_loss_order(replacement_unit)
                if order_id:
                    logger.info(f"✅ PROACTIVE stop-loss placed at unit {replacement_unit}")
                else:
                    logger.error(f"❌ Failed to place PROACTIVE stop-loss at unit {replacement_unit}")
            else:
                logger.debug(f"Already have active order at unit {replacement_unit}, skipping proactive placement")
        
        # Always slide window on unit changes (more aggressive)
        await self._slide_window(event.direction)
    
    async def _slide_window(self, direction: str):
        """Slide the order window incrementally based on price movement"""
        current_unit = self.unit_tracker.current_unit
        phase = self.unit_tracker.phase
        window_state = self.unit_tracker.get_window_state()
        
        # MORE AGGRESSIVE: Slide based on direction and window composition
        # Don't strictly require specific phases
        
        if direction == 'up':
            # Moving up: Maintain stop-loss window
            # Check if we have mostly sells (stop-losses) in window
            if len(window_state['sell_orders']) >= 2:  # At least half are sells
                # Add stop-loss at (current-1), cancel at (current-5)
                new_unit = current_unit - 1  
                old_unit = current_unit - 5
                
                logger.info(f"📈 Sliding window UP (phase={phase}): adding stop-loss at unit {new_unit}, cancelling at unit {old_unit}")
                
                # Ensure new unit exists
                if new_unit not in self.position_map:
                    add_unit_level(self.position_state, self.position_map, new_unit)
                
                # Cancel the old order first
                if old_unit in self.position_map and self.position_map[old_unit].is_active:
                    success = await self._cancel_order(old_unit)
                    if success:
                        logger.info(f"✅ Cancelled old stop-loss at unit {old_unit}")
                
                # Place new stop-loss order (if not already placed by proactive logic)
                if not self.position_map[new_unit].is_active:
                    order_id = await self._place_stop_loss_order(new_unit)
                    if order_id:
                        logger.info(f"✅ Slid window up: Added stop-loss at unit {new_unit}")
                    else:
                        logger.error(f"❌ Failed to place stop-loss at unit {new_unit}")
            else:
                logger.debug(f"Not sliding up: only {len(window_state['sell_orders'])} sell orders in window")
        
        elif direction == 'down':
            # Moving down: Maintain limit buy window
            # Check if we have mostly buys in window
            if len(window_state['buy_orders']) >= 2:  # At least half are buys
                # Add limit buy at (current+1), cancel at (current+5)
                new_unit = current_unit + 1
                old_unit = current_unit + 5
                
                logger.info(f"📉 Sliding window DOWN (phase={phase}): adding limit buy at unit {new_unit}, cancelling at unit {old_unit}")
                
                # Ensure new unit exists
                if new_unit not in self.position_map:
                    add_unit_level(self.position_state, self.position_map, new_unit)
                
                # Cancel the old order first  
                if old_unit in self.position_map and self.position_map[old_unit].is_active:
                    success = await self._cancel_order(old_unit)
                    if success:
                        logger.info(f"✅ Cancelled old limit buy at unit {old_unit}")
                
                # Place new limit buy order (if not already placed by proactive logic)
                if not self.position_map[new_unit].is_active:
                    order_id = await self._place_limit_buy_order(new_unit)
                    if order_id:
                        logger.info(f"✅ Slid window down: Added limit buy at unit {new_unit}")
                    else:
                        logger.error(f"❌ Failed to place limit buy at unit {new_unit}")
            else:
                logger.debug(f"Not sliding down: only {len(window_state['buy_orders'])} buy orders in window")
            
        window_state = self.unit_tracker.get_window_state()
        logger.info(f"Window after slide: {window_state}")
    
    async def _cancel_order(self, unit: int) -> bool:
        """Cancel an order at a specific unit"""
        config = self.position_map[unit]
        if config.order_id:
            # Cancel via SDK
            success = self.sdk_client.cancel_order(self.symbol, config.order_id)
            if success:
                config.mark_cancelled()
                logger.info(f"Cancelled order at unit {unit}")
                return True
            else:
                logger.error(f"Failed to cancel order at unit {unit}")
                return False
        return False
    
    async def handle_order_fill(self, order_id: str, filled_price: Decimal, filled_size: Decimal):
        """Handle order fill notification"""
        # Find the unit that was filled
        filled_unit = None
        filled_order_type = None
        
        for unit, config in self.position_map.items():
            if config.order_id == order_id:
                filled_unit = unit
                filled_order_type = config.order_type
                config.mark_filled(filled_price, filled_size)
                break
        
        if filled_unit is not None:
            logger.info(f"Order filled at unit {filled_unit}: {filled_order_type.value} {filled_size:.6f} @ ${filled_price:.2f}")
            
            # Update unit tracker
            order_side = "sell" if filled_order_type == OrderType.STOP_LOSS_SELL else "buy"
            self.unit_tracker.handle_order_execution(filled_unit, order_side)
            
            # Determine replacement order based on strategy doc v9
            current_unit = self.unit_tracker.current_unit
            
            if filled_order_type == OrderType.STOP_LOSS_SELL:
                # Stop-loss filled: place limit buy at current+1
                replacement_unit = current_unit + 1
                
                # Ensure unit exists in position map
                if replacement_unit not in self.position_map:
                    add_unit_level(self.position_state, self.position_map, replacement_unit)
                
                # Place limit buy order
                order_id = await self._place_limit_buy_order(replacement_unit)
                if order_id:
                    logger.info(f"✅ Placed replacement limit buy at unit {replacement_unit}")
                else:
                    logger.error(f"❌ Failed to place replacement limit buy at unit {replacement_unit}")
                    
            elif filled_order_type == OrderType.LIMIT_BUY:
                # Limit buy filled: place stop-loss at current-1
                replacement_unit = current_unit - 1
                
                # Ensure unit exists in position map
                if replacement_unit not in self.position_map:
                    add_unit_level(self.position_state, self.position_map, replacement_unit)
                
                # Place stop-loss order
                order_id = await self._place_stop_loss_order(replacement_unit)
                if order_id:
                    logger.info(f"✅ Placed replacement stop-loss at unit {replacement_unit}")
                else:
                    logger.error(f"❌ Failed to place replacement stop-loss at unit {replacement_unit}")
            
            # Check for phase transition
            window_state = self.unit_tracker.get_window_state()
            if window_state['phase'] == 'RESET':
                await self._handle_reset()
    
    async def _handle_reset(self):
        """Handle RESET phase - capture compound growth"""
        logger.info("🔄 RESET triggered - capturing compound growth")
        
        # Get current position value
        positions = self.sdk_client.get_positions()
        if self.symbol in positions:
            position = positions[self.symbol]
            new_position_value = position.size * self.current_price
            
            # Reset unit tracker with new position value
            self.unit_tracker.reset_for_new_cycle(self.current_price)
            
            # Update position state with new values for fresh cycle
            self.position_state.position_value_usd = new_position_value
            self.position_state.asset_size = position.size
            # Update original sizes for the new cycle (compound growth)
            self.position_state.original_asset_size = position.size
            self.position_state.original_position_value_usd = new_position_value
            # Recalculate fragments based on new original sizes
            self.position_state.long_fragment_usd = new_position_value / Decimal("4")
            self.position_state.long_fragment_asset = position.size / Decimal("4")
            
            # Cancel all existing orders
            for unit, config in self.position_map.items():
                if config.is_active:
                    await self._cancel_order(unit)
            
            # Place new window orders
            await self._place_window_orders()
            
            logger.info(f"RESET complete - New position value: ${new_position_value:.2f}")
    
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
                active_orders = len(get_active_orders(self.position_map))
                
                logger.debug(f"Status - Phase: {window_state['phase']}, Active orders: {active_orders}, Current unit: {window_state['current_unit']}")
                
                # Sleep for monitoring interval
                await asyncio.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.is_running = False
            await self.shutdown()
    
    async def shutdown(self):
        """Clean shutdown of all components"""
        logger.info("Shutting down HyperTrader...")
        
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
    parser.add_argument("--wallet", choices=["long", "hedge"], required=True, help="Wallet type")
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