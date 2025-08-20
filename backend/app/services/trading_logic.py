import logging
from decimal import Decimal
from typing import Optional, Tuple
import asyncio

from app.models.state import SystemState, PhaseType
from app.services.exchange import exchange_manager, OrderResult

logger = logging.getLogger(__name__)


class TradingLogic:
    """
    Core trading logic implementing the four-phase hedging strategy.
    This is the heart of the HyperTrader system.
    """
    
    def __init__(self):
        self.exchange = exchange_manager
    
    async def on_unit_change(self, state: SystemState, new_unit: int, current_price: Decimal) -> SystemState:
        """
        Central traffic cop function called when unit changes.
        Determines phase and calls appropriate handler.
        
        Args:
            state: Current system state
            new_unit: New current unit
            current_price: Current market price
            
        Returns:
            Updated system state
        """
        logger.info(f"Unit change detected for {state.symbol}: {state.current_unit} -> {new_unit}")
        
        # Update current unit and price tracking
        state.current_unit = new_unit
        
        # Update peak/valley tracking
        state = self._update_peak_valley_tracking(state, current_price)
        
        # Determine required phase
        required_phase = self._determine_phase(state)
        
        # Update phase if changed
        if state.current_phase != required_phase:
            logger.info(f"Phase change for {state.symbol}: {state.current_phase} -> {required_phase}")
            state.current_phase = required_phase
        
        # Call appropriate phase handler
        try:
            if state.current_phase == "advance":
                state = await self._handle_advance_phase(state, current_price)
            elif state.current_phase == "retracement":
                state = await self._handle_retracement_phase(state, current_price)
            elif state.current_phase == "decline":
                state = await self._handle_decline_phase(state, current_price)
            elif state.current_phase == "recovery":
                state = await self._handle_recovery_phase(state, current_price)
            
        except Exception as e:
            logger.error(f"Error in phase handler for {state.symbol}: {e}")
            raise
        
        # Check for system reset conditions
        if state.is_reset_condition_met():
            logger.info(f"Reset conditions met for {state.symbol}")
            state = await self._perform_system_reset(state, current_price)
        
        return state
    
    def _update_peak_valley_tracking(self, state: SystemState, current_price: Decimal) -> SystemState:
        """Update peak and valley price tracking"""
        
        # Peak tracking (when we have long positions)
        if state.long_invested > 0:
            if state.peak_unit is None:
                state.peak_unit = state.current_unit
                state.peak_price = current_price
            elif state.current_unit > state.peak_unit:
                state.peak_unit = state.current_unit
                state.peak_price = current_price
        else:
            state.peak_unit = None
            state.peak_price = None
        
        # Valley tracking (when we have short positions)
        if state.hedge_short > 0:
            if state.valley_unit is None:
                state.valley_unit = state.current_unit
                state.valley_price = current_price
            elif state.current_unit < state.valley_unit:
                state.valley_unit = state.current_unit
                state.valley_price = current_price
        else:
            state.valley_unit = None
            state.valley_price = None
        
        return state
    
    def _determine_phase(self, state: SystemState) -> PhaseType:
        """Determine the required phase based on allocation states"""
        
        total_long = state.long_invested + state.long_cash
        total_hedge = state.hedge_long + abs(state.hedge_short)
        
        # ADVANCE: Both allocations fully long
        if (state.long_invested == total_long and 
            state.hedge_long == total_hedge and 
            state.hedge_short == 0):
            return "advance"
        
        # DECLINE: Long fully cashed, hedge fully short
        if (state.long_invested == 0 and 
            state.long_cash == total_long and
            state.hedge_long == 0 and 
            state.hedge_short == total_hedge):
            return "decline"
        
        # RECOVERY: Recovery from valley (hedge has shorts to unwind)
        if state.hedge_short > 0 and state.valley_unit is not None:
            return "recovery"
        
        # RETRACEMENT: Default when declining from peak
        return "retracement"
    
    async def _handle_advance_phase(self, state: SystemState, current_price: Decimal) -> SystemState:
        """
        Handle ADVANCE phase: Track peaks, no trades
        Both allocations are fully long, building positions during uptrends
        """
        logger.debug(f"Handling ADVANCE phase for {state.symbol}")
        
        # No trades in advance phase, just track the peak progression
        # Peak tracking is handled in _update_peak_valley_tracking
        
        return state
    
    async def _handle_retracement_phase(self, state: SystemState, current_price: Decimal) -> SystemState:
        """
        Handle RETRACEMENT phase: Scale positions based on distance from peak
        Hedge scales immediately, Long waits for confirmation
        """
        logger.debug(f"Handling RETRACEMENT phase for {state.symbol}")
        
        if state.peak_unit is None:
            logger.warning(f"No peak unit set for {state.symbol} in retracement phase")
            return state
        
        units_from_peak = state.current_unit - state.peak_unit
        
        # Check if choppy trading is active
        choppy_trading = state.is_choppy_trading_active()
        
        # Handle Long Allocation (with confirmation unless choppy)
        if not choppy_trading and units_from_peak == -1:
            # Wait for confirmation - no action on first unit drop
            logger.debug(f"Long allocation waiting for confirmation at {units_from_peak} units from peak")
        else:
            # Scale long allocation (confirmed decline or choppy trading)
            if units_from_peak <= -2 or (choppy_trading and units_from_peak <= -1):
                state = await self._scale_long_allocation(state, units_from_peak, current_price)
        
        # Handle Hedge Allocation (immediate response)
        if units_from_peak <= -1:
            state = await self._scale_hedge_allocation(state, units_from_peak, current_price)
        
        return state
    
    async def _handle_decline_phase(self, state: SystemState, current_price: Decimal) -> SystemState:
        """
        Handle DECLINE phase: Hold positions, let shorts compound gains
        Long allocation 100% cash, hedge allocation 100% short
        """
        logger.debug(f"Handling DECLINE phase for {state.symbol}")
        
        # No trades in decline phase - positions are held to compound gains
        # Continue tracking valleys for eventual recovery
        
        return state
    
    async def _handle_recovery_phase(self, state: SystemState, current_price: Decimal) -> SystemState:
        """
        Handle RECOVERY phase: Systematic re-entry from valleys
        Hedge unwinds shorts immediately, Long re-enters with confirmation
        """
        logger.debug(f"Handling RECOVERY phase for {state.symbol}")
        
        if state.valley_unit is None:
            logger.warning(f"No valley unit set for {state.symbol} in recovery phase")
            return state
        
        units_from_valley = state.current_unit - state.valley_unit
        
        # Check if choppy trading is active
        choppy_trading = state.is_choppy_trading_active()
        
        # Handle Long Allocation (with confirmation unless choppy)
        if not choppy_trading and units_from_valley == 1:
            # Wait for confirmation - no action on first unit rise
            logger.debug(f"Long allocation waiting for confirmation at {units_from_valley} units from valley")
        else:
            # Re-enter long allocation (confirmed recovery or choppy trading)
            if units_from_valley >= 2 or (choppy_trading and units_from_valley >= 1):
                state = await self._re_enter_long_allocation(state, units_from_valley, current_price)
        
        # Handle Hedge Allocation (immediate response)
        if units_from_valley >= 1:
            state = await self._unwind_hedge_shorts(state, units_from_valley, current_price)
        
        return state
    
    async def _scale_long_allocation(self, state: SystemState, units_from_peak: int, current_price: Decimal) -> SystemState:
        """Scale down long allocation during retracement"""
        
        total_long = state.long_invested + state.long_cash
        if total_long == 0:
            return state
        
        # Calculate target percentage based on units from peak
        target_percent = max(0, 100 + (units_from_peak + 2) * 25)  # -2 units = 75%, -3 = 50%, etc.
        current_percent = (state.long_invested / total_long) * 100
        
        if abs(target_percent - current_percent) > 5:  # 5% tolerance
            # Calculate amount to sell
            target_invested = total_long * (target_percent / 100)
            amount_to_sell = state.long_invested - target_invested
            
            if amount_to_sell > 0:
                # Execute sell order
                position_size = amount_to_sell / current_price  # Convert dollars to position size
                
                result = await self.exchange.place_order(
                    symbol=state.symbol,
                    order_type="market",
                    side="sell",
                    amount=position_size,
                    reduce_only=True
                )
                
                if result.success:
                    actual_amount = result.cost or amount_to_sell
                    state.long_invested -= actual_amount
                    state.long_cash += actual_amount
                    
                    logger.info(f"Long allocation scaled: sold ${actual_amount} at {current_price}")
                else:
                    logger.error(f"Failed to scale long allocation: {result.error_message}")
        
        return state
    
    async def _scale_hedge_allocation(self, state: SystemState, units_from_peak: int, current_price: Decimal) -> SystemState:
        """Scale hedge allocation during retracement (sell long, go short)"""
        
        total_hedge = state.hedge_long + abs(state.hedge_short)
        if total_hedge == 0:
            return state
        
        # Calculate target percentages
        units_down = abs(units_from_peak)
        target_long_percent = max(0, 100 - units_down * 25)  # -1 unit = 75%, -2 = 50%, etc.
        target_short_percent = min(100, units_down * 25)     # -1 unit = 25%, -2 = 50%, etc.
        
        current_long_percent = (state.hedge_long / total_hedge) * 100 if total_hedge > 0 else 0
        
        if abs(target_long_percent - current_long_percent) > 5:  # 5% tolerance
            # Calculate position changes needed
            target_long_amount = total_hedge * (target_long_percent / 100)
            target_short_amount = total_hedge * (target_short_percent / 100)
            
            long_change = target_long_amount - state.hedge_long
            short_change = target_short_amount - abs(state.hedge_short)
            
            # Execute position changes
            if long_change < 0:  # Reduce long position
                position_size = abs(long_change) / current_price
                
                result = await self.exchange.place_order(
                    symbol=state.symbol,
                    order_type="market",
                    side="sell",
                    amount=position_size
                )
                
                if result.success:
                    actual_amount = result.cost or abs(long_change)
                    state.hedge_long -= actual_amount
                    
            if short_change > 0:  # Increase short position
                position_size = short_change / current_price
                
                result = await self.exchange.place_order(
                    symbol=state.symbol,
                    order_type="market",
                    side="sell",
                    amount=position_size
                )
                
                if result.success:
                    actual_amount = result.cost or short_change
                    state.hedge_short += actual_amount
        
        return state
    
    async def _re_enter_long_allocation(self, state: SystemState, units_from_valley: int, current_price: Decimal) -> SystemState:
        """Re-enter long allocation during recovery"""
        
        total_long = state.long_invested + state.long_cash
        if total_long == 0 or state.long_cash == 0:
            return state
        
        # Calculate target percentage
        target_percent = min(100, (units_from_valley - 1) * 25)  # +2 units = 25%, +3 = 50%, etc.
        current_percent = (state.long_invested / total_long) * 100
        
        if target_percent > current_percent:
            # Calculate amount to buy
            target_invested = total_long * (target_percent / 100)
            amount_to_buy = target_invested - state.long_invested
            
            if amount_to_buy > 0 and amount_to_buy <= state.long_cash:
                position_size = amount_to_buy / current_price
                
                result = await self.exchange.place_order(
                    symbol=state.symbol,
                    order_type="market",
                    side="buy",
                    amount=position_size
                )
                
                if result.success:
                    actual_amount = result.cost or amount_to_buy
                    state.long_invested += actual_amount
                    state.long_cash -= actual_amount
                    
                    logger.info(f"Long allocation re-entered: bought ${actual_amount} at {current_price}")
        
        return state
    
    async def _unwind_hedge_shorts(self, state: SystemState, units_from_valley: int, current_price: Decimal) -> SystemState:
        """Unwind hedge short positions during recovery"""
        
        if state.hedge_short == 0:
            return state
        
        total_hedge = state.hedge_long + abs(state.hedge_short)
        
        # Calculate target percentages
        target_long_percent = min(100, units_from_valley * 25)  # +1 unit = 25%, +2 = 50%, etc.
        target_short_percent = max(0, 100 - units_from_valley * 25)
        
        target_short_amount = total_hedge * (target_short_percent / 100)
        short_reduction = abs(state.hedge_short) - target_short_amount
        
        if short_reduction > 0:
            position_size = short_reduction / current_price
            
            # Cover shorts by buying
            result = await self.exchange.place_order(
                symbol=state.symbol,
                order_type="market",
                side="buy",
                amount=position_size
            )
            
            if result.success:
                actual_amount = result.cost or short_reduction
                state.hedge_short -= actual_amount
                state.hedge_long += actual_amount
                
                logger.info(f"Hedge shorts unwound: covered ${actual_amount} at {current_price}")
        
        return state
    
    async def _perform_system_reset(self, state: SystemState, current_price: Decimal) -> SystemState:
        """
        Perform system reset when conditions are met.
        Recalculates total portfolio value and resets all variables.
        """
        logger.info(f"Performing system reset for {state.symbol}")
        
        try:
            # Calculate total portfolio value
            total_value = state.get_total_portfolio_value()
            
            # Split 50/50 between allocations
            allocation_amount = total_value / 2
            
            # Reset all tracking variables
            state.current_unit = 0
            state.peak_unit = None
            state.valley_unit = None
            state.peak_price = None
            state.valley_price = None
            
            # Reset allocation amounts
            state.long_invested = allocation_amount
            state.long_cash = Decimal("0")
            state.hedge_long = allocation_amount
            state.hedge_short = Decimal("0")
            
            # Update reference price to current price
            state.entry_price = current_price
            
            # Recalculate unit value based on new portfolio size
            # Unit value = 5% of new total margin with leverage
            state.unit_value = (total_value * Decimal("0.05")) / state.leverage
            
            # Reset phase to advance
            state.current_phase = "advance"
            
            logger.info(f"System reset complete for {state.symbol}. New portfolio value: ${total_value}")
            
        except Exception as e:
            logger.error(f"Error during system reset for {state.symbol}: {e}")
            raise
        
        return state


# Global trading logic instance
trading_logic = TradingLogic()