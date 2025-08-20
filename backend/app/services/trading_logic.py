# backend/app/services/trading_logic.py

from decimal import Decimal
from app.models.state import SystemState
from app.services.exchange import ExchangeManager

# --- Utility Functions ---

def calculate_unit_value(purchase_price: Decimal, leverage: int, desired_percentage: int = 5) -> Decimal:
    """
    Calculates the price movement required to generate a 5% profit on margin.
    """
    if leverage == 0:
        return Decimal('Infinity')
    required_asset_increase = Decimal(desired_percentage) / Decimal(leverage)
    return purchase_price * (required_asset_increase / Decimal(100))

# --- Phase Handlers ---

def handle_advance_phase(state: SystemState, current_price: Decimal) -> SystemState:
    """
    Logic for the ADVANCE phase. No trades are executed.
    The system holds the position and updates the peak if a new high is reached.
    """
    new_unit = int((current_price - state.entry_price) / state.unit_value)
    
    if new_unit > state.peak_unit:
        state.peak_unit = new_unit
        state.peak_price = current_price
        
    state.current_unit = new_unit
    return state

def handle_retracement_phase(state: SystemState, exchange: ExchangeManager) -> SystemState:
    """
    Logic for the RETRACEMENT phase.
    - Hedge allocation scales out immediately on 1-unit drops.
    - Long allocation waits for a 2-unit drop confirmation before scaling out.
    """
    # This function would contain the logic to place sell orders
    # based on the distance from peak_unit.
    # For brevity, the core logic is described. A full implementation would be complex.
    
    # Example logic for a -2 unit drop from peak:
    # 1. Hedge sells another 25%
    # 2. Long sells its first 25%
    # await exchange.place_order(...)
    
    print(f"Handling RETRACEMENT for {state.symbol}")
    return state

def handle_decline_phase(state: SystemState, current_price: Decimal) -> SystemState:
    """
    Logic for the DECLINE phase. No trades are executed.
    The system is fully defensive and tracks for a new valley (bottom).
    """
    new_unit = int((current_price - state.entry_price) / state.unit_value)

    if state.valley_unit is None or new_unit < state.valley_unit:
        state.valley_unit = new_unit
        state.valley_price = current_price
        
    state.current_unit = new_unit
    return state

def handle_recovery_phase(state: SystemState, exchange: ExchangeManager) -> SystemState:
    """
    Logic for the RECOVERY phase.
    - Hedge allocation scales in immediately on 1-unit recoveries.
    - Long allocation waits for a 2-unit recovery confirmation before scaling in.
    """
    # This function would contain the logic to cover shorts and buy longs.
    print(f"Handling RECOVERY for {state.symbol}")
    return state

def perform_system_reset(state: SystemState, current_price: Decimal) -> SystemState:
    """
    Resets the system state after a full recovery, compounding profits.
    """
    # 1. Calculate total portfolio value (simplified)
    total_value = state.long_invested + state.hedge_long
    
    # 2. Rebalance allocations
    state.long_invested = total_value / Decimal(2)
    state.hedge_long = total_value / Decimal(2)
    state.long_cash = Decimal(0)
    state.hedge_short = Decimal(0)
    
    # 3. Reset tracking variables
    state.entry_price = current_price
    state.unit_value = calculate_unit_value(current_price, 10) # Assuming 10x leverage
    state.current_phase = 'advance'
    state.current_unit = 0
    state.peak_unit = 0
    state.peak_price = current_price
    state.valley_unit = None
    state.valley_price = None
    
    print(f"--- SYSTEM RESET for {state.symbol} ---")
    return state

# --- Central Controller ---

async def on_unit_change(state: SystemState, current_price: Decimal, exchange: ExchangeManager) -> SystemState:
    """
    The main "traffic cop" function. It determines the correct phase and
    triggers the appropriate logic handler.
    """
    previous_unit = state.current_unit
    new_unit = int((current_price - state.entry_price) / state.unit_value)

    if new_unit == previous_unit:
        return state # No action if a full unit hasn't changed

    state.current_unit = new_unit

    # Determine the correct phase
    if state.long_invested == Decimal(0):
        phase = 'decline'
    elif new_unit < state.peak_unit:
        phase = 'retracement'
    elif state.valley_unit is not None and new_unit > state.valley_unit:
        phase = 'recovery'
    else:
        phase = 'advance'
        
    state.current_phase = phase

    # Call the appropriate handler
    if state.current_phase == 'advance':
        state = handle_advance_phase(state, current_price)
    elif state.current_phase == 'retracement':
        state = handle_retracement_phase(state, exchange)
    elif state.current_phase == 'decline':
        state = handle_decline_phase(state, current_price)
    elif state.current_phase == 'recovery':
        state = handle_recovery_phase(state, exchange)

    # Check for system reset condition
    if state.long_cash == Decimal(0) and state.hedge_short == Decimal(0) and state.current_phase != 'advance':
       # This condition might need refinement to trigger correctly after full recovery
       pass

    return state