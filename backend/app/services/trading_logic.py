from decimal import Decimal
from loguru import logger

from app.models.state import SystemState, PhaseType
from app.services.exchange import exchange_manager
from app.core.logging import get_trade_logger

class TradingLogic:
    """
    Encapsulates the 4-phase trading strategy logic, including placing orders.
    """

    # --- Unit Calculation Parameters (Manual Price Movement) ---
    # The fixed amount the price must move to constitute one "unit".
    # This value should be manually set based on the asset's volatility and price.
    # NOTE: This should ideally be loaded from configuration and stored in the SystemState.
    UNIT_PRICE_MOVEMENT: Decimal = Decimal("0.0025") # Example for an asset like ARB

    def __init__(self, state: SystemState):
        self.state = state
        self.trade_logger = get_trade_logger(state.symbol)

    async def run(self, current_price: Decimal, sync_first_run: bool = False) -> SystemState:
        """
        Main entry point to run the trading logic for a price update.
        """
        if not self.state.is_active:
            return self.state

        # Sync with exchange positions on first run or when requested
        if sync_first_run:
            await self.sync_state_with_exchange()

        # Log every price update for debugging
        previous_price = self.state.current_price
        self.state.current_price = current_price
        previous_unit = self.state.current_unit
        
        # Always log price updates to track system activity
        self.trade_logger.info(f"PRICE: ${previous_price} → ${current_price} "
                              f"(Phase: {self.state.current_phase}, Unit: {previous_unit})")
        
        self._update_current_unit()

        # Only run phase logic if the unit has changed
        if self.state.current_unit != previous_unit:
            self.trade_logger.info(f"🔄 UNIT CHANGE: {previous_unit} → {self.state.current_unit} "
                                  f"(Price: ${current_price}, Phase: {self.state.current_phase})")
            
            if self.state.current_phase == "advance":
                await self._handle_advance_phase()
            elif self.state.current_phase == "retracement":
                await self._handle_retracement_phase()
            elif self.state.current_phase == "decline":
                await self._handle_decline_phase()
            elif self.state.current_phase == "recovery":
                await self._handle_recovery_phase()
        else:
            # Log when no unit change occurs so you can see the system is running
            self.trade_logger.debug(f"PRICE: No unit change (still {self.state.current_unit}) - "
                                   f"Price: ${current_price}, Phase: {self.state.current_phase}")
        
        return self.state

    def _update_current_unit(self):
        """
        Calculates the current unit based on user-defined unit_size.
        The unit_size represents how much the price must move to constitute one unit.
        """
        unit_size = self.state.unit_size

        if unit_size <= 0:
            self.state.current_unit = 0
            self.trade_logger.warning(f"UNIT: Invalid unit_size {unit_size}, setting current_unit to 0")
            return

        # Calculate how many "units" the price has moved from entry price
        total_price_change = self.state.current_price - self.state.entry_price
        new_unit = int(total_price_change / unit_size)
        
        # Log unit calculation details
        self.trade_logger.info(f"UNIT: Price=${self.state.current_price}, Entry=${self.state.entry_price}, "
                              f"Change=${total_price_change}, Unit_size=${unit_size}, "
                              f"Calculated_unit={total_price_change / unit_size:.2f}, "
                              f"Final_unit={new_unit}")
        
        self.state.current_unit = new_unit

    def _transition_to(self, new_phase: PhaseType):
        """Handles state transitions."""
        if self.state.current_phase != new_phase:
            self.trade_logger.info(f"TRADE: Phase transition from {self.state.current_phase} to {new_phase}")
            self.state.current_phase = new_phase

    async def _adjust_position(self, side: str, amount_usd: Decimal, reduce_only: bool = False, allocation: str = "hedge"):
        """Helper function to place orders and update state."""
        if amount_usd < self.state.MIN_TRADE_VALUE:
            self.trade_logger.info(f"TRADE: Trade amount ${amount_usd} is below minimum. Skipping.")
            return

        amount_in_coins = amount_usd / self.state.current_price
        amount_rounded = round(float(amount_in_coins), 6)

        self.trade_logger.info(
            f"TRADE: Placing {side} order - Amount: ${amount_usd:.2f} "
            f"({amount_rounded} coins), Reduce-only: {reduce_only}, Phase: {self.state.current_phase}, Allocation: {allocation}"
        )

        order_result = await exchange_manager.place_order(
            symbol=self.state.symbol,
            order_type="market",
            side=side,
            amount=amount_rounded,
            price=self.state.current_price,
            params={"reduceOnly": reduce_only}
        )

        if order_result.success:
            self.trade_logger.info(
                f"TRADE: Successfully placed {side} order for ${amount_usd:.2f}. "
                f"Order ID: {getattr(order_result, 'order_id', 'N/A')}"
            )
            
            # Update the state's allocation values based on the successful order
            self._update_state_after_order(side, amount_usd, reduce_only, allocation)
            
        else:
            self.trade_logger.error(
                f"TRADE: Failed to place {side} order for ${amount_usd:.2f}: "
                f"{order_result.error_message}"
            )

    def _update_state_after_order(self, side: str, amount_usd: Decimal, reduce_only: bool, allocation: str):
        """Update state allocations after a successful order."""
        if allocation == "hedge":
            if side == "buy":
                if reduce_only:
                    # Covering shorts - reduce short position, money goes back to main long position
                    self.state.hedge_short = max(Decimal("0"), self.state.hedge_short - amount_usd)
                    self.state.long_invested += amount_usd
                    self.trade_logger.info(f"TRADE: State updated - Hedge short reduced by ${amount_usd}, long invested increased to ${self.state.long_invested}")
                else:
                    # Opening new long - this shouldn't happen in our simplified strategy
                    self.state.hedge_long += amount_usd
                    self.trade_logger.info(f"TRADE: State updated - Hedge long increased to ${self.state.hedge_long}")
            elif side == "sell":
                if reduce_only:
                    # Selling hedge longs - this shouldn't happen often in our simplified strategy
                    self.state.hedge_long = max(Decimal("0"), self.state.hedge_long - amount_usd)
                    self.trade_logger.info(f"TRADE: State updated - Hedge long reduced to ${self.state.hedge_long}")
                else:
                    # Opening new short - increase short position
                    self.state.hedge_short += amount_usd
                    self.trade_logger.info(f"TRADE: State updated - Hedge short increased to ${self.state.hedge_short}")
                    
        elif allocation == "long":
            if side == "buy":
                # Long allocation buying - move cash to invested
                buy_amount = min(amount_usd, self.state.long_cash)
                self.state.long_cash -= buy_amount
                self.state.long_invested += buy_amount
                self.trade_logger.info(f"TRADE: State updated - Long cash: ${self.state.long_cash}, long invested: ${self.state.long_invested}")
            elif side == "sell":
                if reduce_only:
                    # Long allocation selling - move invested to cash
                    sell_amount = min(amount_usd, self.state.long_invested)
                    self.state.long_invested -= sell_amount
                    self.state.long_cash += sell_amount
                    self.trade_logger.info(f"TRADE: State updated - Long cash: ${self.state.long_cash}, long invested: ${self.state.long_invested}")

        # Log current state totals for debugging
        total_long_allocation = self.state.long_invested + self.state.long_cash
        total_hedge_allocation = self.state.hedge_long + self.state.hedge_short
        self.trade_logger.info(f"TRADE: Current allocations - Long total: ${total_long_allocation}, Hedge total: ${total_hedge_allocation}")


    async def _handle_advance_phase(self):
        """Logic for when the price is advancing."""
        if self.state.peak_unit is None or self.state.current_unit > self.state.peak_unit:
            self.state.peak_unit = self.state.current_unit
            self.state.peak_price = self.state.current_price
            self.trade_logger.info(f"TRADE: New peak in ADVANCE: Unit {self.state.peak_unit} at ${self.state.peak_price}")

        if self.state.current_unit < self.state.peak_unit:
            self._transition_to("retracement")
            # Don't set valley_unit here - that's only for decline phase
            # Start retracement - first 12% chunk gets sold immediately
            if self.state.long_invested > 0:
                total_position_value = self.state.long_invested
                chunk_size = total_position_value * Decimal("0.12")
                await self._adjust_position("sell", chunk_size, reduce_only=True, allocation="long")
                self.trade_logger.info(f"TRADE: Entered retracement - sold first 12% chunk (${chunk_size})")


    async def _handle_retracement_phase(self):
        """Logic for when the price is retracing from a peak."""
        if self.state.current_unit >= self.state.peak_unit:
            self._transition_to("advance")
            return
        
        # Calculate units from peak - but skip unit 1 since that was handled in advance phase
        units_from_peak = self.state.peak_unit - self.state.current_unit
        
        # Simple approach: for each unit down, we should have sold 12% of original position
        # Calculate what our total sales should be
        if units_from_peak > 0:
            # Calculate original position size (current invested + cash + shorts)
            original_position = self.state.long_invested + self.state.long_cash + self.state.hedge_short
            target_sold_amount = original_position * Decimal("0.12") * units_from_peak
            actually_sold = self.state.long_cash + self.state.hedge_short
            
            # If we haven't sold enough, sell more
            if target_sold_amount > actually_sold:
                amount_to_sell = target_sold_amount - actually_sold
                
                if self.state.long_invested >= amount_to_sell:
                    # Sell from long position
                    await self._adjust_position("sell", amount_to_sell, reduce_only=True, allocation="long")
                    self.trade_logger.info(f"TRADE: Retracement - sold ${amount_to_sell} to reach target for {units_from_peak} units")
                elif self.state.long_invested > 0:
                    # Sell remaining long and start shorting
                    remaining_long = self.state.long_invested
                    remaining_to_short = amount_to_sell - remaining_long
                    
                    await self._adjust_position("sell", remaining_long, reduce_only=True, allocation="long")
                    await self._adjust_position("sell", remaining_to_short, reduce_only=False, allocation="hedge")
                    self.trade_logger.info(f"TRADE: Retracement - sold remaining ${remaining_long} long, opened ${remaining_to_short} short")
        
        # Check if we've reached full decline (no long position left)
        if self.state.long_invested == 0:
            self._transition_to("decline")


    async def _handle_decline_phase(self):
        """Logic for when the price is in a confirmed decline."""
        if self.state.valley_unit is None or self.state.current_unit < self.state.valley_unit:
            self.state.valley_unit = self.state.current_unit
            self.state.valley_price = self.state.current_price
            self.trade_logger.info(f"TRADE: New valley in DECLINE: Unit {self.state.valley_unit} at ${self.state.valley_price}")

        if self.state.current_unit > self.state.valley_unit:
            self._transition_to("recovery")
            # Don't set peak_unit here - that's only for advance phase
            # Recovery will handle the 25% buy-back logic


    async def _handle_recovery_phase(self):
        """Logic for when the price is recovering from a valley."""
        if self.state.current_unit <= self.state.valley_unit:
            self._transition_to("decline")
            return
        
        # Calculate units from valley for scaling decisions
        units_from_valley = self.state.current_unit - self.state.valley_unit
        
        # For each unit up from valley, buy back 25% of available defensive positions
        if units_from_valley > 0:
            # Calculate what we should have bought back (25% per unit)
            original_available = self.state.long_cash + self.state.hedge_short
            
            if original_available > 0:
                target_bought_back = original_available * Decimal("0.25") * units_from_valley
                current_available = self.state.long_cash + self.state.hedge_short
                amount_to_buy = min(target_bought_back, current_available)
                
                if amount_to_buy > 0:
                    # Priority 1: Cover shorts first
                    if self.state.hedge_short > 0:
                        short_to_cover = min(amount_to_buy, self.state.hedge_short)
                        await self._adjust_position("buy", short_to_cover, reduce_only=True, allocation="hedge")
                        amount_to_buy -= short_to_cover
                        self.trade_logger.info(f"TRADE: Recovery - covered ${short_to_cover} short position")
                    
                    # Priority 2: Buy long with cash
                    if amount_to_buy > 0 and self.state.long_cash > 0:
                        cash_to_use = min(amount_to_buy, self.state.long_cash)
                        await self._adjust_position("buy", cash_to_use, reduce_only=False, allocation="long")
                        self.trade_logger.info(f"TRADE: Recovery - bought ${cash_to_use} long position with cash")
        
        # Check if we've reached full advance (no shorts, no cash)
        if self.state.hedge_short == 0 and self.state.long_cash == 0:
            self._transition_to("advance")
            self.trade_logger.info("TRADE: Full recovery achieved - transitioning to ADVANCE phase")

    async def sync_state_with_exchange(self):
        """Synchronize the state allocations with actual exchange positions."""
        try:
            positions = await exchange_manager.fetch_positions([self.state.symbol])
            
            if not positions:
                self.trade_logger.info("TRADE: No positions found on exchange for sync")
                return
            
            # Reset allocation tracking
            total_long_value = Decimal("0")
            total_short_value = Decimal("0")
            
            for position in positions:
                if position.symbol == self.state.symbol:
                    position_value = abs(position.notional)
                    
                    if position.side == "long":
                        total_long_value += position_value
                        self.trade_logger.info(f"TRADE: Found long position: ${position_value}")
                    elif position.side == "short":
                        total_short_value += position_value
                        self.trade_logger.info(f"TRADE: Found short position: ${position_value}")
            
            # In ADVANCE phase, all long positions go to long_invested
            # In other phases, we need to figure out the split
            if self.state.current_phase == "advance":
                # Single long position during advance
                self.state.long_invested = total_long_value
                self.state.hedge_long = Decimal("0")
                self.state.hedge_short = total_short_value
                self.state.long_cash = Decimal("0")
            else:
                # During other phases, positions are split between allocations
                # This is a simplified assumption - in practice you'd need better tracking
                self.state.long_invested = total_long_value * Decimal("0.6") if total_long_value > 0 else Decimal("0")
                self.state.hedge_long = total_long_value * Decimal("0.4") if total_long_value > 0 else Decimal("0")
                self.state.hedge_short = total_short_value
                # Assume remaining is cash
                total_position_value = self.state.required_margin
                used_value = self.state.long_invested + self.state.hedge_long + self.state.hedge_short
                self.state.long_cash = max(Decimal("0"), total_position_value - used_value)
            
            self.trade_logger.info(f"TRADE: State synced - Hedge Long: ${self.state.hedge_long}, "
                                 f"Hedge Short: ${self.state.hedge_short}, "
                                 f"Long Invested: ${self.state.long_invested}, "
                                 f"Long Cash: ${self.state.long_cash}")
                                 
        except Exception as e:
            self.trade_logger.error(f"TRADE: Failed to sync state with exchange: {e}")


async def run_trading_logic_for_state(state: SystemState, current_price: Decimal, sync_first_run: bool = False) -> SystemState:
    """
    Takes a SystemState object and a price, runs the logic, and returns the updated state.
    """
    logic_instance = TradingLogic(state)
    updated_state = await logic_instance.run(current_price, sync_first_run)
    return updated_state
