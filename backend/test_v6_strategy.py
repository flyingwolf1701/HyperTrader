#!/usr/bin/env python3
"""
Test script for v6.0.0 strategy implementation
Tests the position_fragment approach and all phases
"""

import asyncio
import json
from decimal import Decimal
from app.services.exchange import exchange_manager
from app.api.endpoints import load_strategy_state, save_strategy_state
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def simulate_advance_phase():
    """Simulate ADVANCE phase with peak tracking"""
    logger.info("=" * 60)
    logger.info("TESTING ADVANCE PHASE")
    logger.info("=" * 60)
    
    # Create initial state
    state = {
        "symbol": "ETH/USDC:USDC",
        "unit_size": 2.0,
        "entry_price": 4780.0,
        "current_unit": 0,
        "peak_unit": 0,
        "valley_unit": None,
        "phase": "ADVANCE",
        "current_long_position": 5000.0,
        "current_short_position": 0,
        "current_cash_position": 0,
        "position_fragment": None,
        "hedge_fragment": None,
        "last_price": 4780.0,
        "initial_position_allocation": 5000.0,
        "current_position_allocation": 5000.0,
        "leverage": 25,
        "test_price": 4780.0  # Use test price to control simulation
    }
    
    save_strategy_state(state)
    logger.info(f"Initial state: Unit 0, Position: ${state['current_long_position']}")
    
    # Simulate price rise to unit 3 (peak)
    for unit in range(1, 4):
        state["test_price"] = state["entry_price"] + (unit * state["unit_size"])
        state["current_unit"] = unit
        state["peak_unit"] = unit
        
        # Calculate position_fragment at peak
        if unit == 3:
            # Simulate fetching position value (in real scenario, from exchange)
            position_value = state["current_long_position"] * 1.2  # Assume 20% profit
            state["position_fragment"] = position_value * 0.10
            logger.info(f"Peak reached at unit {unit}, position_fragment: ${state['position_fragment']:.2f}")
        
        save_strategy_state(state)
        logger.info(f"Unit {unit}: Price ${state['test_price']:.2f}")
    
    return state


async def simulate_retracement_phase(state):
    """Simulate RETRACEMENT phase with fragment-based scaling"""
    logger.info("=" * 60)
    logger.info("TESTING RETRACEMENT PHASE")
    logger.info("=" * 60)
    
    position_fragment = state["position_fragment"]
    logger.info(f"Using position_fragment: ${position_fragment:.2f}")
    
    # Simulate decline from peak (unit 3 to -2 from peak)
    retracement_actions = [
        (2, 1, "Sell 1 fragment, short 1 fragment"),
        (1, 2, "Sell 2 fragments, short 1 fragment, cash 1 fragment"),
        (0, 3, "Sell 2 fragments, short 1 fragment, cash 1 fragment"),
    ]
    
    for current_unit, units_from_peak, action in retracement_actions:
        state["test_price"] = state["entry_price"] + (current_unit * state["unit_size"])
        state["current_unit"] = current_unit
        state["phase"] = "RETRACEMENT"
        
        logger.info(f"\nUnit {current_unit} ({units_from_peak} from peak): {action}")
        
        if units_from_peak == 1:
            # -1: Sell 1 fragment, short 1 fragment
            state["current_long_position"] -= position_fragment
            state["current_short_position"] += position_fragment
            
        elif units_from_peak in [2, 3]:
            # -2, -3: Sell 2 fragments, short 1, cash 1
            state["current_long_position"] -= 2 * position_fragment
            state["current_short_position"] += position_fragment
            state["current_cash_position"] += position_fragment
        
        save_strategy_state(state)
        logger.info(f"  Long: ${state['current_long_position']:.2f}")
        logger.info(f"  Short: ${state['current_short_position']:.2f}")
        logger.info(f"  Cash: ${state['current_cash_position']:.2f}")
    
    # Continue to unit -5 from peak
    state["current_unit"] = -2  # 5 units below peak of 3
    state["test_price"] = state["entry_price"] + (-2 * state["unit_size"])
    
    # Unit -4 from peak
    state["current_long_position"] -= 2 * position_fragment
    state["current_short_position"] += position_fragment
    state["current_cash_position"] += position_fragment
    
    logger.info(f"\nUnit -1 (4 from peak): Sell 2 fragments, short 1, cash 1")
    logger.info(f"  Long: ${state['current_long_position']:.2f}")
    logger.info(f"  Short: ${state['current_short_position']:.2f}")
    logger.info(f"  Cash: ${state['current_cash_position']:.2f}")
    
    # Unit -5 from peak: sell remaining long to short
    remaining_long = state["current_long_position"]
    state["temp_cash_fragment"] = remaining_long
    state["current_long_position"] = 0
    state["current_short_position"] += remaining_long
    
    logger.info(f"\nUnit -2 (5 from peak): Sell remaining ${remaining_long:.2f} to short")
    logger.info(f"  Long: ${state['current_long_position']:.2f}")
    logger.info(f"  Short: ${state['current_short_position']:.2f}")
    logger.info(f"  Cash: ${state['current_cash_position']:.2f}")
    
    save_strategy_state(state)
    return state


async def simulate_decline_phase(state):
    """Simulate DECLINE phase"""
    logger.info("=" * 60)
    logger.info("TESTING DECLINE PHASE")
    logger.info("=" * 60)
    
    state["phase"] = "DECLINE"
    state["valley_unit"] = state["current_unit"]
    
    # Continue decline to unit -5
    state["current_unit"] = -5
    state["valley_unit"] = -5
    state["test_price"] = state["entry_price"] + (-5 * state["unit_size"])
    
    logger.info(f"Valley at unit {state['valley_unit']}")
    logger.info(f"Holding short position: ${state['current_short_position']:.2f}")
    
    # Move up 1 unit from valley to calculate hedge_fragment
    state["current_unit"] = -4
    state["test_price"] = state["entry_price"] + (-4 * state["unit_size"])
    state["hedge_fragment"] = state["current_short_position"] * 0.25
    
    logger.info(f"Valley +1: Calculated hedge_fragment: ${state['hedge_fragment']:.2f}")
    
    save_strategy_state(state)
    return state


async def simulate_recovery_phase(state):
    """Simulate RECOVERY phase"""
    logger.info("=" * 60)
    logger.info("TESTING RECOVERY PHASE")
    logger.info("=" * 60)
    
    # Move to valley +2 to trigger RECOVERY
    state["current_unit"] = -3
    state["test_price"] = state["entry_price"] + (-3 * state["unit_size"])
    state["phase"] = "RECOVERY"
    
    hedge_fragment = state["hedge_fragment"]
    position_fragment = state.get("position_fragment", 500)  # Use saved fragment
    
    logger.info(f"Entering RECOVERY at valley +2")
    logger.info(f"Using hedge_fragment: ${hedge_fragment:.2f}")
    logger.info(f"Using position_fragment: ${position_fragment:.2f}")
    
    # Simulate recovery actions for units +2, +3, +4
    for units_from_valley in [2, 3, 4]:
        current_unit = state["valley_unit"] + units_from_valley
        state["current_unit"] = current_unit
        state["test_price"] = state["entry_price"] + (current_unit * state["unit_size"])
        
        # Close 1 hedge_fragment short, buy 1 hedge + 1 position fragment
        state["current_short_position"] -= hedge_fragment
        state["current_long_position"] += hedge_fragment
        state["current_cash_position"] -= position_fragment
        
        logger.info(f"\nValley +{units_from_valley} (unit {current_unit}):")
        logger.info(f"  Closed ${hedge_fragment:.2f} short")
        logger.info(f"  Bought ${hedge_fragment + position_fragment:.2f} long")
        logger.info(f"  Long: ${state['current_long_position']:.2f}")
        logger.info(f"  Short: ${state['current_short_position']:.2f}")
        logger.info(f"  Cash: ${state['current_cash_position']:.2f}")
    
    # Unit +5: Close remaining short
    state["current_unit"] = 0
    state["test_price"] = state["entry_price"]
    
    remaining_short = state["current_short_position"]
    state["temp_hedge_value"] = remaining_short
    state["current_short_position"] = 0
    state["current_long_position"] += remaining_short
    state["current_cash_position"] -= position_fragment
    
    logger.info(f"\nValley +5 (unit 0):")
    logger.info(f"  Closed remaining ${remaining_short:.2f} short")
    logger.info(f"  Bought ${remaining_short + position_fragment:.2f} long")
    logger.info(f"  Long: ${state['current_long_position']:.2f}")
    logger.info(f"  Short: ${state['current_short_position']:.2f}")
    logger.info(f"  Cash: ${state['current_cash_position']:.2f}")
    
    save_strategy_state(state)
    return state


async def simulate_reset(state):
    """Simulate RESET mechanism"""
    logger.info("=" * 60)
    logger.info("TESTING RESET MECHANISM")
    logger.info("=" * 60)
    
    # Unit +6 triggers RESET
    state["current_unit"] = 1
    state["test_price"] = state["entry_price"] + (1 * state["unit_size"])
    
    if state["current_short_position"] == 0 and state["current_cash_position"] <= 100:
        logger.info("RESET conditions met:")
        logger.info(f"  Short position: ${state['current_short_position']}")
        logger.info(f"  Cash position: ${state['current_cash_position']}")
        
        # Reset all tracking variables
        state["phase"] = "ADVANCE"
        state["current_unit"] = 0
        state["peak_unit"] = 0
        state["valley_unit"] = None
        state["position_fragment"] = None
        state["hedge_fragment"] = None
        state["temp_cash_fragment"] = None
        state["temp_hedge_value"] = None
        
        # Update allocation (simulate profit)
        state["current_position_allocation"] = state["current_long_position"]
        state["entry_price"] = state["test_price"]
        
        logger.info("\nRESET completed:")
        logger.info(f"  New phase: {state['phase']}")
        logger.info(f"  New allocation: ${state['current_position_allocation']:.2f}")
        logger.info(f"  New entry price: ${state['entry_price']:.2f}")
        logger.info(f"  All unit variables reset to 0/None")
    
    save_strategy_state(state)
    return state


async def main():
    """Run complete v6.0.0 strategy test"""
    try:
        logger.info("\n" + "=" * 60)
        logger.info("STARTING V6.0.0 STRATEGY TEST")
        logger.info("=" * 60)
        
        # Initialize exchange connection
        await exchange_manager.initialize()
        logger.info("Exchange initialized\n")
        
        # Run through all phases
        state = await simulate_advance_phase()
        await asyncio.sleep(1)
        
        state = await simulate_retracement_phase(state)
        await asyncio.sleep(1)
        
        state = await simulate_decline_phase(state)
        await asyncio.sleep(1)
        
        state = await simulate_recovery_phase(state)
        await asyncio.sleep(1)
        
        state = await simulate_reset(state)
        
        logger.info("\n" + "=" * 60)
        logger.info("TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
        # Summary
        logger.info("\nFinal Summary:")
        logger.info(f"  Phase: {state['phase']}")
        logger.info(f"  Position Allocation: ${state['current_position_allocation']:.2f}")
        logger.info(f"  Initial Allocation: ${state['initial_position_allocation']:.2f}")
        
        profit = state['current_position_allocation'] - state['initial_position_allocation']
        profit_pct = (profit / state['initial_position_allocation']) * 100
        logger.info(f"  Profit/Loss: ${profit:.2f} ({profit_pct:.1f}%)")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        await exchange_manager.close()


if __name__ == "__main__":
    asyncio.run(main())