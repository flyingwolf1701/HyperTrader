"""Trading logic service implementing the four-phase strategy."""

from typing import Optional
from app.models.state import SystemState
from app.services.exchange import ExchangeService

class TradingLogicService:
    """Service implementing the advanced hedging strategy logic."""
    
    def __init__(self, exchange_service: ExchangeService):
        """Initialize trading logic service."""
        self.exchange = exchange_service
    
    def calculate_unit_price(self, purchase_price: float, leverage: int, desired_percentage: float = 5.0) -> float:
        """Calculate the required price increase to hit a profit target with leverage."""
        required_asset_increase_percent = desired_percentage / leverage
        price_increase = purchase_price * (required_asset_increase_percent / 100)
        return price_increase
    
    def determine_phase(self, state: SystemState) -> str:
        """Determine current trading phase based on system state."""
        long_total = state.long_invested + state.long_cash
        hedge_total = state.hedge_long + state.hedge_short
        
        # ADVANCE: Both allocations 100% long
        if (state.long_invested == long_total and 
            state.hedge_long == hedge_total and 
            state.hedge_short == 0):
            return "ADVANCE"
        
        # DECLINE: Long fully cashed, hedge fully short
        if (state.long_invested == 0 and 
            state.long_cash == long_total and
            state.hedge_long == 0 and 
            state.hedge_short == hedge_total):
            return "DECLINE"
        
        # RECOVERY: Recovery from valley
        if state.valley_unit is not None and state.current_unit > state.valley_unit:
            return "RECOVERY"
        
        # RETRACEMENT: Default for partial positions
        return "RETRACEMENT"
    
    def detect_choppy_conditions(self, state: SystemState) -> bool:
        """Detect if system is in choppy trading conditions."""
        long_total = state.long_invested + state.long_cash
        hedge_total = state.hedge_long + state.hedge_short
        
        # Long allocation partially allocated
        long_partial = 0 < state.long_invested < long_total
        
        # Hedge allocation partially allocated
        hedge_partial = (0 < state.hedge_long < hedge_total and state.hedge_short > 0)
        
        return long_partial or hedge_partial
