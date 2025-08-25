"""
Strategy Manager - Stage 4: Enter Trade & ADVANCE Phase
Coordinates WebSocket price tracking with exchange operations
"""
import asyncio
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

from ..core.models import UnitTracker, Phase
from ..core.websocket_client import HyperliquidWebSocketClient
from ..exchange.exchange_client import HyperliquidExchangeClient
from ..utils.config import settings


class StrategyState:
    """Holds the complete state of a trading strategy"""
    
    def __init__(self, symbol: str, position_size_usd: Decimal, unit_size: Decimal, leverage: int = 10):
        # Configuration
        self.symbol = symbol
        self.position_size_usd = position_size_usd
        self.unit_size = unit_size
        self.leverage = leverage
        
        # Position tracking
        self.position_allocation = position_size_usd  # Current position value
        self.initial_position_allocation = position_size_usd  # Original position size
        
        # Fragment calculations (for future phases)
        self.position_fragment = Decimal("0")  # 10% of position value
        self.hedge_fragment = Decimal("0")  # 25% of short position value
        
        # RESET tracking
        self.reset_count = 0  # Number of resets completed
        self.pre_reset_value = position_size_usd  # Value before last reset
        
        # Entry tracking
        self.entry_price: Optional[Decimal] = None
        self.entry_time: Optional[datetime] = None
        self.has_position = False
        
        # Unit tracker
        self.unit_tracker = UnitTracker(unit_size=unit_size)
        
    def calculate_position_fragment(self):
        """Calculate 10% of current position value"""
        self.position_fragment = self.position_allocation * Decimal("0.10")
        return self.position_fragment
    
    def calculate_hedge_fragment(self, short_value: Decimal):
        """Calculate 25% of short position value for RECOVERY phase"""
        self.hedge_fragment = short_value * Decimal("0.25")
        return self.hedge_fragment


class StrategyManager:
    """
    Manages the complete trading strategy
    Stage 4: Enter Trade & ADVANCE Phase
    """
    
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.ws_client = HyperliquidWebSocketClient(testnet=testnet)
        self.exchange_client = HyperliquidExchangeClient(testnet=testnet)
        self.strategies: Dict[str, StrategyState] = {}
        self.is_running = False
        
    async def start_strategy(
        self,
        symbol: str,
        position_size_usd: Decimal,
        unit_size: Decimal,
        leverage: int = 10
    ) -> bool:
        """
        Start a trading strategy for a symbol
        Stage 4: Enter trade and begin ADVANCE phase
        
        Args:
            symbol: Trading pair (e.g., "ETH/USDC:USDC")
            position_size_usd: Position size in USD
            unit_size: Price movement per unit in USD
            leverage: Leverage to use
        """
        try:
            logger.info("=" * 60)
            logger.info(f"Starting Strategy - Stage 4: Enter Trade & ADVANCE")
            logger.info(f"Symbol: {symbol}")
            logger.info(f"Position Size: ${position_size_usd}")
            logger.info(f"Unit Size: ${unit_size}")
            logger.info(f"Leverage: {leverage}x")
            logger.info("=" * 60)
            
            # Check if strategy already exists
            if symbol in self.strategies:
                logger.warning(f"Strategy already running for {symbol}")
                return False
            
            # Create strategy state
            state = StrategyState(symbol, position_size_usd, unit_size, leverage)
            self.strategies[symbol] = state
            
            # Check existing position
            existing_position = self.exchange_client.get_position(symbol)
            if existing_position:
                logger.warning(f"Existing position found for {symbol}")
                logger.info(f"Position: {existing_position['side']} {existing_position['contracts']}")
                logger.info("Please close existing position before starting new strategy")
                return False
            
            # Enter trade (100% long position)
            logger.info("\nPhase: ENTERING TRADE")
            logger.info("Opening 100% long position...")
            
            order = self.exchange_client.open_long(
                symbol=symbol,
                position_size_usd=position_size_usd,
                leverage=leverage
            )
            
            if order:
                # Update state
                state.has_position = True
                state.entry_time = datetime.now()
                
                # Get actual entry price from order
                if "price" in order:
                    state.entry_price = Decimal(str(order["price"]))
                else:
                    # Fallback to current market price
                    state.entry_price = self.exchange_client.get_current_price(symbol)
                
                # Set entry price in unit tracker
                state.unit_tracker.entry_price = state.entry_price
                
                # Calculate initial position fragment (10% of position)
                state.calculate_position_fragment()
                
                logger.success(f"✅ Position opened successfully")
                logger.info(f"Entry Price: ${state.entry_price:.2f}")
                logger.info(f"Order ID: {order.get('id', 'N/A')}")
                logger.info(f"Position Fragment: ${state.position_fragment:.2f}")
                
                # Set phase to ADVANCE
                state.unit_tracker.phase = Phase.ADVANCE
                logger.info(f"\nPhase: ADVANCE")
                logger.info("Monitoring for price increases...")
                logger.info("Peak unit will be tracked as price rises")
                logger.info("Position fragment will be recalculated on each unit change")
                
                # Start WebSocket monitoring
                await self._start_monitoring(symbol, unit_size)
                
                return True
            else:
                logger.error("Failed to open position")
                del self.strategies[symbol]
                return False
                
        except Exception as e:
            logger.error(f"Error starting strategy: {e}")
            if symbol in self.strategies:
                del self.strategies[symbol]
            return False
    
    async def _start_monitoring(self, symbol: str, unit_size: Decimal):
        """Start WebSocket monitoring for price changes"""
        try:
            # Connect WebSocket if not connected
            if not self.ws_client.is_connected:
                await self.ws_client.connect()
            
            # Subscribe to trades with custom callback
            # For now, we'll use the basic tracking
            # In future stages, we'll add phase-specific callbacks
            coin = symbol.split("/")[0]  # Extract coin from symbol
            await self.ws_client.subscribe_to_trades(coin, unit_size)
            
            logger.info(f"Started monitoring {coin} prices")
            
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
    
    async def handle_advance_phase(self, symbol: str):
        """
        Handle ADVANCE phase logic
        - Track peak units
        - Recalculate position fragment on unit changes
        - Monitor for phase transition
        """
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        
        # Get current position value
        position = self.exchange_client.get_position(symbol)
        if position:
            # Update position allocation with current value
            current_price = self.exchange_client.get_current_price(symbol)
            state.position_allocation = position["contracts"] * current_price
            
            # Recalculate position fragment (10% of current value)
            state.calculate_position_fragment()
            
            logger.info(f"ADVANCE Phase Update:")
            logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
            logger.info(f"  Peak Unit: {state.unit_tracker.peak_unit}")
            logger.info(f"  Position Value: ${state.position_allocation:.2f}")
            logger.info(f"  Position Fragment: ${state.position_fragment:.2f}")
            
            # Check for phase transition to RETRACEMENT
            units_from_peak = state.unit_tracker.get_units_from_peak()
            if units_from_peak <= -1:
                logger.warning(f"Price dropped {abs(units_from_peak)} unit(s) from peak")
                logger.info("Transitioning to RETRACEMENT phase")
                state.unit_tracker.phase = Phase.RETRACEMENT
                await self.handle_retracement_phase(symbol)
    
    async def handle_retracement_phase(self, symbol: str):
        """
        Handle RETRACEMENT phase logic
        Stage 5: Execute pre-defined actions based on units from peak
        
        Actions by units from peak:
        -1: Sell 1 fragment long, Open 1 fragment short
        -2: Sell 2 fragments long, Add 1 fragment short  
        -3: Sell 2 fragments long, Add 1 fragment short
        -4: Sell 2 fragments long, Add 1 fragment short
        -5: Sell remaining long, Add proceeds to short
        -6: Enter DECLINE phase
        """
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        units_from_peak = state.unit_tracker.get_units_from_peak()
        
        logger.info("=" * 60)
        logger.info(f"RETRACEMENT Phase - {abs(units_from_peak)} units from peak")
        logger.info("=" * 60)
        
        try:
            current_price = self.exchange_client.get_current_price(symbol)
            
            if units_from_peak == -1:
                # -1: Sell 1 fragment long, Open 1 fragment short
                logger.info("Action: Sell 1 fragment long, Open 1 fragment short")
                
                # Calculate amounts
                fragment_size = state.position_fragment / current_price
                
                # Reduce long by 1 fragment
                order = self.exchange_client.reduce_position(
                    symbol=symbol,
                    amount=fragment_size,
                    side="sell"
                )
                if order:
                    logger.success(f"Reduced long by 1 fragment: {fragment_size:.6f} ETH")
                
                # Open short position with 1 fragment
                order = self.exchange_client.open_short(
                    symbol=symbol,
                    position_size_usd=state.position_fragment,
                    leverage=state.leverage
                )
                if order:
                    logger.success(f"Opened short with 1 fragment: ${state.position_fragment:.2f}")
                
                logger.info("Portfolio: ~80% Long / 10% Short / 10% Cash")
                
            elif units_from_peak == -2:
                # -2: Sell 2 fragments long, Add 1 fragment short
                logger.info("Action: Sell 2 fragments long, Add 1 fragment short")
                
                # Calculate amounts
                fragment_size = state.position_fragment / current_price
                
                # Reduce long by 2 fragments
                order = self.exchange_client.reduce_position(
                    symbol=symbol,
                    amount=fragment_size * 2,
                    side="sell"
                )
                if order:
                    logger.success(f"Reduced long by 2 fragments: {fragment_size * 2:.6f} ETH")
                
                # Add to short position with 1 fragment
                order = self.exchange_client.add_to_position(
                    symbol=symbol,
                    position_size_usd=state.position_fragment,
                    side="sell"
                )
                if order:
                    logger.success(f"Added to short with 1 fragment: ${state.position_fragment:.2f}")
                
                logger.info("Portfolio: ~50% Long / 20% Short / 30% Cash")
                
            elif units_from_peak == -3:
                # -3: Sell 2 fragments long, Add 1 fragment short
                logger.info("Action: Sell 2 fragments long, Add 1 fragment short")
                
                fragment_size = state.position_fragment / current_price
                
                # Reduce long by 2 fragments
                order = self.exchange_client.reduce_position(
                    symbol=symbol,
                    amount=fragment_size * 2,
                    side="sell"
                )
                if order:
                    logger.success(f"Reduced long by 2 fragments: {fragment_size * 2:.6f} ETH")
                
                # Add to short position with 1 fragment
                order = self.exchange_client.add_to_position(
                    symbol=symbol,
                    position_size_usd=state.position_fragment,
                    side="sell"
                )
                if order:
                    logger.success(f"Added to short with 1 fragment: ${state.position_fragment:.2f}")
                
                logger.info("Portfolio: ~20% Long / 30% Short / 50% Cash")
                
            elif units_from_peak == -4:
                # -4: Sell 2 fragments long, Add 1 fragment short
                logger.info("Action: Sell 2 fragments long, Add 1 fragment short")
                
                fragment_size = state.position_fragment / current_price
                
                # Reduce long by 2 fragments
                order = self.exchange_client.reduce_position(
                    symbol=symbol,
                    amount=fragment_size * 2,
                    side="sell"
                )
                if order:
                    logger.success(f"Reduced long by 2 fragments: {fragment_size * 2:.6f} ETH")
                
                # Add to short position with 1 fragment
                order = self.exchange_client.add_to_position(
                    symbol=symbol,
                    position_size_usd=state.position_fragment,
                    side="sell"
                )
                if order:
                    logger.success(f"Added to short with 1 fragment: ${state.position_fragment:.2f}")
                
                logger.info("Portfolio: ~0% Long / 40% Short / 60% Cash")
                
            elif units_from_peak == -5:
                # -5: Sell remaining long, Add proceeds to short
                logger.info("Action: Sell remaining long, Add proceeds to short")
                
                # Get current long position
                position = self.exchange_client.get_position(symbol)
                if position and position["side"] == "long":
                    # Close entire long position
                    order = self.exchange_client.close_position(symbol)
                    if order:
                        logger.success(f"Closed remaining long position")
                    
                    # Add the proceeds to short (approximately 2 fragments worth)
                    order = self.exchange_client.add_to_position(
                        symbol=symbol,
                        position_size_usd=state.position_fragment * 2,
                        side="sell"
                    )
                    if order:
                        logger.success(f"Added remaining proceeds to short: ${state.position_fragment * 2:.2f}")
                
                logger.info("Portfolio: 0% Long / ~50% Short / ~50% Cash")
                
            elif units_from_peak <= -6:
                # -6 and below: Enter DECLINE phase
                logger.info("Transitioning to DECLINE phase")
                state.unit_tracker.phase = Phase.DECLINE
                state.unit_tracker.valley_unit = state.unit_tracker.current_unit
                logger.info("Position is now fully defensive (short + cash)")
                await self.handle_decline_phase(symbol)
                
        except Exception as e:
            logger.error(f"Error in RETRACEMENT phase: {e}")
    
    async def handle_decline_phase(self, symbol: str):
        """
        Handle DECLINE phase logic - Stage 7
        
        The portfolio is defensive (short + cash) and profits from continued decline
        
        Actions:
        - Track valley unit as price continues to fall
        - Hold short position to accumulate profits
        - Calculate hedge_fragment when price begins to recover
        - Transition to RECOVERY phase when price rises +2 from valley
        """
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        
        # Get current position
        position = self.exchange_client.get_position(symbol)
        if not position:
            logger.error("No position found in DECLINE phase")
            return
        
        current_price = self.exchange_client.get_current_price(symbol)
        
        # Update valley if we've made a new low
        if state.unit_tracker.current_unit < state.unit_tracker.valley_unit:
            state.unit_tracker.valley_unit = state.unit_tracker.current_unit
            logger.info(f"New valley unit: {state.unit_tracker.valley_unit}")
        
        # Calculate current short position value
        short_value = Decimal(str(position["contracts"])) * current_price
        
        # Calculate hedge fragment (25% of short position value)
        state.calculate_hedge_fragment(short_value)
        
        logger.info("=" * 60)
        logger.info("DECLINE Phase Status")
        logger.info("=" * 60)
        logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
        logger.info(f"  Valley Unit: {state.unit_tracker.valley_unit}")
        logger.info(f"  Units from Valley: {state.unit_tracker.get_units_from_valley()}")
        logger.info(f"  Short Position Value: ${short_value:.2f}")
        logger.info(f"  Hedge Fragment: ${state.hedge_fragment:.2f}")
        
        # Calculate unrealized profit on short
        if position["side"] == "short" and position.get("entryPrice"):
            entry_price = Decimal(str(position["entryPrice"]))
            short_profit = (entry_price - current_price) * Decimal(str(position["contracts"]))
            logger.info(f"  Short Position P&L: ${short_profit:.2f}")
        
        # Check for phase transition to RECOVERY
        units_from_valley = state.unit_tracker.get_units_from_valley()
        
        if units_from_valley >= 2:
            logger.info("=" * 60)
            logger.info(f"Price recovered {units_from_valley} units from valley")
            logger.info("Transitioning to RECOVERY phase")
            state.unit_tracker.phase = Phase.RECOVERY
            # Stage 8 will implement RECOVERY phase
            logger.info("Stage 8 will handle position scaling during recovery")
        else:
            logger.info(f"\nHolding defensive position...")
            logger.info(f"Will transition to RECOVERY at +2 units from valley")
            logger.info(f"Current: {units_from_valley} units from valley")
    
    async def monitor_price_change(self, symbol: str, new_price: Decimal):
        """
        Monitor price changes and trigger appropriate phase handlers
        Called when WebSocket detects unit changes
        """
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        previous_unit = state.unit_tracker.current_unit
        
        # Update unit tracker with new price
        unit_changed = state.unit_tracker.calculate_unit_change(new_price)
        
        if not unit_changed:
            return
        
        logger.info(f"Unit changed: {previous_unit} -> {state.unit_tracker.current_unit}")
        
        # Handle based on current phase
        if state.unit_tracker.phase == Phase.ADVANCE:
            await self.handle_advance_phase(symbol)
        elif state.unit_tracker.phase == Phase.RETRACEMENT:
            await self.handle_retracement_phase(symbol)
        elif state.unit_tracker.phase == Phase.DECLINE:
            await self.handle_decline_phase(symbol)
        elif state.unit_tracker.phase == Phase.RECOVERY:
            # Stage 8 will implement this
            logger.info("RECOVERY phase handler will be implemented in Stage 8")
    
    async def handle_reset_mechanism(self, symbol: str):
        """
        Handle RESET mechanism - Stage 6
        Re-calibrates the strategy after completing a full cycle
        
        Trigger: Position becomes 100% long (after RECOVERY or manual reset)
        
        Process:
        1. Reset all unit tracking variables
        2. Update position allocation to current value (lock in profits/losses)
        3. Enter ADVANCE phase with new baseline
        """
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        
        logger.info("=" * 60)
        logger.info("RESET MECHANISM TRIGGERED")
        logger.info("=" * 60)
        
        try:
            # Get current position value
            position = self.exchange_client.get_position(symbol)
            if not position:
                logger.error("No position found for reset")
                return
            
            current_price = self.exchange_client.get_current_price(symbol)
            current_value = Decimal(str(position["contracts"])) * current_price
            
            # Calculate profit/loss from cycle
            cycle_pnl = current_value - state.position_allocation
            cycle_pnl_pct = (cycle_pnl / state.position_allocation) * Decimal("100")
            
            logger.info(f"Cycle Summary:")
            logger.info(f"  Starting Value: ${state.position_allocation:.2f}")
            logger.info(f"  Current Value: ${current_value:.2f}")
            logger.info(f"  Cycle P&L: ${cycle_pnl:.2f} ({cycle_pnl_pct:.2f}%)")
            logger.info(f"  Reset Count: {state.reset_count}")
            
            # Store pre-reset value
            state.pre_reset_value = state.position_allocation
            
            # UPDATE POSITION ALLOCATION TO CURRENT VALUE
            # This is the key - profits/losses are now locked into the new baseline
            state.position_allocation = current_value
            state.initial_position_allocation = current_value  # New baseline
            
            # RESET ALL UNIT TRACKING VARIABLES
            state.unit_tracker.current_unit = 0
            state.unit_tracker.peak_unit = 0
            state.unit_tracker.valley_unit = 0
            
            # Update entry price to current price (new baseline)
            state.entry_price = current_price
            state.unit_tracker.entry_price = current_price
            
            # Recalculate fragments based on new position value
            state.calculate_position_fragment()
            
            # Set phase to ADVANCE
            state.unit_tracker.phase = Phase.ADVANCE
            
            # Increment reset counter
            state.reset_count += 1
            
            logger.success("RESET Complete!")
            logger.info(f"New Baseline:")
            logger.info(f"  Position Value: ${state.position_allocation:.2f}")
            logger.info(f"  Entry Price: ${state.entry_price:.2f}")
            logger.info(f"  Position Fragment: ${state.position_fragment:.2f}")
            logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
            logger.info(f"  Phase: {state.unit_tracker.phase.value}")
            logger.info(f"  Total Resets: {state.reset_count}")
            
            logger.info("\nStrategy re-calibrated and ready for next cycle")
            logger.info("Entering ADVANCE phase with compounded position")
            
        except Exception as e:
            logger.error(f"Error in RESET mechanism: {e}")
    
    async def trigger_reset_if_needed(self, symbol: str) -> bool:
        """
        Check if RESET should be triggered
        
        Trigger condition: Position is 100% long and we've completed a cycle
        This typically happens after RECOVERY phase or can be manually triggered
        """
        if symbol not in self.strategies:
            return False
        
        state = self.strategies[symbol]
        
        # Check if we're 100% long
        position = self.exchange_client.get_position(symbol)
        if not position or position["side"] != "long":
            return False
        
        # Check if we've completed a cycle (been through other phases)
        # RESET is triggered when returning to 100% long after RECOVERY
        # or when manually requested
        if state.reset_count > 0 or state.unit_tracker.valley_unit != 0:
            # We've been through a cycle
            logger.info("RESET conditions met: 100% long position after cycle")
            await self.handle_reset_mechanism(symbol)
            return True
        
        return False
    
    async def get_strategy_status(self, symbol: str) -> Dict[str, Any]:
        """Get current status of a strategy"""
        if symbol not in self.strategies:
            return {"error": f"No strategy found for {symbol}"}
        
        state = self.strategies[symbol]
        
        # Get current position from exchange
        position = self.exchange_client.get_position(symbol)
        
        # Get current price
        current_price = self.exchange_client.get_current_price(symbol)
        
        return {
            "symbol": symbol,
            "phase": state.unit_tracker.phase.value,
            "entry_price": float(state.entry_price) if state.entry_price else None,
            "current_price": float(current_price),
            "current_unit": state.unit_tracker.current_unit,
            "peak_unit": state.unit_tracker.peak_unit,
            "valley_unit": state.unit_tracker.valley_unit,
            "units_from_peak": state.unit_tracker.get_units_from_peak(),
            "position": {
                "has_position": state.has_position,
                "side": position["side"] if position else None,
                "contracts": float(position["contracts"]) if position else 0,
                "pnl": float(position["unrealizedPnl"]) if position else 0
            },
            "position_fragment": float(state.position_fragment),
            "position_allocation": float(state.position_allocation),
            "reset_count": state.reset_count,
            "initial_allocation": float(state.initial_position_allocation)
        }
    
    async def stop_strategy(self, symbol: str, close_position: bool = True):
        """
        Stop a running strategy
        
        Args:
            symbol: Trading pair
            close_position: Whether to close the position
        """
        if symbol not in self.strategies:
            logger.warning(f"No strategy running for {symbol}")
            return
        
        state = self.strategies[symbol]
        
        logger.info(f"Stopping strategy for {symbol}")
        
        # Close position if requested
        if close_position and state.has_position:
            logger.info("Closing position...")
            try:
                order = self.exchange_client.close_position(symbol)
                if order:
                    logger.success(f"Position closed. Order ID: {order.get('id', 'N/A')}")
            except Exception as e:
                logger.error(f"Error closing position: {e}")
        
        # Remove strategy
        del self.strategies[symbol]
        logger.info(f"Strategy stopped for {symbol}")