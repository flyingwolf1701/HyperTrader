from decimal import Decimal
from loguru import logger

from app.models.state import SystemState, PhaseType
from app.services.exchange import exchange_manager
from app.core.logging import get_trade_logger

class TradingLogic:
    """
    Encapsulates the 4-phase trading strategy logic, including placing orders.
    """

    def __init__(self, state: SystemState):
        self.state = state
        self.trade_logger = get_trade_logger(state.symbol)

    async def run(self, current_price: Decimal) -> SystemState:
        """
        Main entry point to run the trading logic for a price update.
        """
        if not self.state.is_active:
            return self.state

        self.state.current_price = current_price
        previous_unit = self.state.current_unit
        self._update_current_unit()

        # Only run phase logic if the unit has changed
        if self.state.current_unit != previous_unit:
            self.trade_logger.info(f"TRADE: Unit changed from {previous_unit} to {self.state.current_unit}. Price: ${current_price}")
            
            if self.state.current_phase == "advance":
                await self._handle_advance_phase()
            elif self.state.current_phase == "retracement":
                await self._handle_retracement_phase()
            elif self.state.current_phase == "decline":
                await self._handle_decline_phase()
            elif self.state.current_phase == "recovery":
                await self._handle_recovery_phase()
        
        return self.state

    def _update_current_unit(self):
        """Calculates the current unit based on price movement."""
        price_change = self.state.current_price - self.state.entry_price
        self.state.current_unit = int(price_change / self.state.unit_value)

    def _transition_to(self, new_phase: PhaseType):
        """Handles state transitions."""
        if self.state.current_phase != new_phase:
            self.trade_logger.info(f"TRADE: Phase transition from {self.state.current_phase} to {new_phase}")
            self.state.current_phase = new_phase

    async def _adjust_position(self, side: str, amount_usd: Decimal, reduce_only: bool = False):
        """Helper function to place orders and update state."""
        if amount_usd < self.state.MIN_TRADE_VALUE:
            self.trade_logger.info(f"TRADE: Trade amount ${amount_usd} is below minimum. Skipping.")
            return

        amount_in_coins = amount_usd / self.state.current_price
        amount_rounded = round(float(amount_in_coins), 6)

        self.trade_logger.info(
            f"TRADE: Placing {side} order - Amount: ${amount_usd:.2f} "
            f"({amount_rounded} coins), Reduce-only: {reduce_only}, Phase: {self.state.current_phase}"
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
            # TODO: Update the state's invested/cash values based on the fill
            # This part needs to be implemented for full accuracy
        else:
            self.trade_logger.error(
                f"TRADE: Failed to place {side} order for ${amount_usd:.2f}: "
                f"{order_result.error_message}"
            )


    async def _handle_advance_phase(self):
        """Logic for when the price is advancing."""
        if self.state.peak_unit is None or self.state.current_unit > self.state.peak_unit:
            self.state.peak_unit = self.state.current_unit
            self.state.peak_price = self.state.current_price
            self.trade_logger.info(f"TRADE: New peak in ADVANCE: Unit {self.state.peak_unit} at ${self.state.peak_price}")

        if self.state.current_unit < self.state.peak_unit:
            self._transition_to("retracement")
            self.state.valley_unit = self.state.current_unit
            self.state.valley_price = self.state.current_price
            # In retracement, we start selling our hedge position
            await self._adjust_position("sell", self.state.hedge_long * Decimal("0.25"), reduce_only=True)


    async def _handle_retracement_phase(self):
        """Logic for when the price is retracing from a peak."""
        if self.state.current_unit >= self.state.peak_unit:
            self._transition_to("advance")
            self.state.valley_unit = None
            self.state.valley_price = None
        
        elif self.state.current_unit <= self.state.peak_unit - 2:
            self._transition_to("decline")
            # In a confirmed decline, we sell the rest of the hedge and start shorting
            await self._adjust_position("sell", self.state.hedge_long, reduce_only=True) # Close remaining long hedge
            await self._adjust_position("sell", self.state.required_margin * Decimal("0.5")) # Open short hedge


    async def _handle_decline_phase(self):
        """Logic for when the price is in a confirmed decline."""
        if self.state.valley_unit is None or self.state.current_unit < self.state.valley_unit:
            self.state.valley_unit = self.state.current_unit
            self.state.valley_price = self.state.current_price
            self.trade_logger.info(f"TRADE: New valley in DECLINE: Unit {self.state.valley_unit} at ${self.state.valley_price}")

        if self.state.current_unit > self.state.valley_unit:
            self._transition_to("recovery")
            self.state.peak_unit = self.state.current_unit
            self.state.peak_price = self.state.current_price
            # In recovery, we start buying back our short position
            await self._adjust_position("buy", self.state.hedge_short * Decimal("0.25"), reduce_only=True)


    async def _handle_recovery_phase(self):
        """Logic for when the price is recovering from a valley."""
        if self.state.current_unit <= self.state.valley_unit:
            self._transition_to("decline")
        
        elif self.state.current_unit >= self.state.valley_unit + 2:
            self._transition_to("advance")
            # In a confirmed advance, we buy back the rest of the short and go long on the hedge
            await self._adjust_position("buy", self.state.hedge_short, reduce_only=True) # Close remaining short hedge
            await self._adjust_position("buy", self.state.required_margin * Decimal("0.5")) # Open long hedge


async def run_trading_logic_for_state(state: SystemState, current_price: Decimal) -> SystemState:
    """
    Takes a SystemState object and a price, runs the logic, and returns the updated state.
    """
    logic_instance = TradingLogic(state)
    updated_state = await logic_instance.run(current_price)
    return updated_state
