# backend/test_strategy.py

import asyncio
from decimal import Decimal
import logging

# Configure logging to see the output from the trading logic
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# We need to import the core components of our application
from app.models.state import SystemState
from app.services.trading_logic import trading_logic
from app.services.exchange import exchange_manager

# --- Mocking Dependencies ---
# To test the logic in isolation, we create "mock" objects for the parts
# we don't want to run, like the WebSocket broadcaster and the real exchange.

class MockWebSocketManager:
    """A fake WebSocket manager that just prints messages instead of sending them."""
    async def broadcast(self, message: str):
        # In a real test, you might check the content of the message.
        # For now, we'll just log that it tried to send something.
        logging.info(f"[WebSocket Broadcast]: {message[:150]}...") # Print first 150 chars

class MockOrderResult:
    """Mock order result for testing."""
    def __init__(self, success=True, order_id=None, cost=None, error_message=None):
        self.success = success
        self.order_id = order_id
        self.cost = cost
        self.error_message = error_message

class MockExchangeManager:
    """A fake exchange manager that pretends to execute trades."""
    async def place_order(self, symbol, order_type, side, amount, **kwargs):
        logging.info(f"[EXCHANGE] ---> Pretending to place {side} {order_type} order for {amount} {symbol}")
        # Return a successful result so the logic continues
        return MockOrderResult(success=True, order_id="mock_order_123", cost=Decimal(str(amount * 3000)))

async def run_strategy_test():
    """
    Main function to run the trading strategy simulation.
    """
    print("--- Initializing Strategy Test ---")

    # --- 1. Setup the Test Environment ---
    
    # Replace the real managers with our fake ones for this test
    trading_logic.exchange = MockExchangeManager()
    
    # Create a test system state
    state = SystemState(
        symbol="LINK",
        entry_price=Decimal("15.0"),
        unit_value=Decimal("0.50"),  # Smaller unit value to see more activity
        initial_margin=Decimal("100.0"),
        leverage=10
    )
    
    # Set initial allocations (50/50 split of $100 margin)
    initial_allocation = Decimal("50.0")
    state.long_invested = initial_allocation
    state.hedge_long = initial_allocation
    state.long_cash = Decimal("0")
    state.hedge_short = Decimal("0")
    state.current_unit = 0
    
    print(f"Initial State: Symbol={state.symbol}, Entry Price=${state.entry_price}, Unit Value=${state.unit_value:.4f}")
    print("-" * 50)

    # --- 2. Simulate Price Movements ---
    
    # Prices are chosen to demonstrate phase changes.
    # Each price will trigger the on_price_update function.
    simulated_prices = [
        # Upward trend (should stay in 'advance')
        15.5, 16.0, 16.5, 
        # Peak and start of a small dip (should enter 'retracement')
        16.8, 16.4, 16.2,
        # A larger drop (should continue retracement, scaling out)
        15.8, 15.1,
        # A significant decline (should enter 'decline' phase)
        14.5, 14.0, 13.5,
        # Bottom out and start to recover (should enter 'recovery')
        13.2, 13.6, 14.1,
        # Strong recovery (should continue re-entering positions)
        14.8, 15.5,
    ]

    for price in simulated_prices:
        current_price = Decimal(str(price))
        print(f"\n---> Simulating new price: ${price}")
        
        # Calculate new unit based on price change
        price_change = current_price - state.entry_price
        new_unit = int(price_change / state.unit_value)
        
        print(f"    Price change: {price_change}, Unit calc: {price_change}/{state.unit_value} = {float(price_change/state.unit_value)} -> Unit: {new_unit}")
        
        # Only trigger logic if unit actually changed
        if new_unit != state.current_unit:
            print(f"    UNIT CHANGE: {state.current_unit} -> {new_unit}")
            state = await trading_logic.on_unit_change(state, new_unit, current_price)
        else:
            print(f"    No unit change (still {state.current_unit})")
        
        # Print a summary of the state after the logic has run
        print(f"    New State: Unit={state.current_unit}, Phase='{state.current_phase}'")
        print(f"    Long Allocation: Invested=${state.long_invested:.2f}, Cash=${state.long_cash:.2f}")
        print(f"    Hedge Allocation: Long=${state.hedge_long:.2f}, Short=${state.hedge_short:.2f}")
        print(f"    Peak/Valley: Peak Unit={state.peak_unit}, Valley Unit={state.valley_unit}")
        print("-" * 50)
        await asyncio.sleep(0.5) # Pause briefly to make the log readable

    print("\n--- Strategy Test Complete ---")


import pytest

@pytest.mark.asyncio
async def test_strategy_simulation():
    """Test the trading strategy with simulated price movements."""
    await run_strategy_test()

if __name__ == "__main__":
    # Run the asynchronous test function
    asyncio.run(run_strategy_test())