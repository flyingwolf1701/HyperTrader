#!/usr/bin/env python3
"""
Test the ADVANCE phase fragment locking logic
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add src to path  
sys.path.append(str(Path(__file__).parent / "src"))

from src.strategy.strategy_manager import StrategyState
from src.core.models import UnitTracker, Phase

async def test_advance_phase_logic():
    """Test the ADVANCE phase logic"""
    
    print("Testing ADVANCE Phase Fragment Locking Logic")
    print("=" * 60)
    
    # Create strategy state
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("2500"),
        unit_size=Decimal("5"),
        leverage=25
    )
    
    # Set initial entry price
    entry_price = Decimal("4575")
    state.unit_tracker.entry_price = entry_price
    state.unit_tracker.phase = Phase.ADVANCE
    
    print(f"Initial Setup:")
    print(f"  Entry Price: ${entry_price}")
    print(f"  Current Unit: {state.unit_tracker.current_unit}")
    print(f"  Peak Unit: {state.unit_tracker.peak_unit}")
    print(f"  Fragment USD: ${state.position_fragment_usd}")
    print(f"  Fragment ETH: {state.position_fragment_eth}")
    print()
    
    # Simulate price going up by 1 unit
    new_price = entry_price + Decimal("5")  # +1 unit at $5/unit
    print(f"Price moves up to: ${new_price} (+1 unit)")
    
    # Update unit tracker
    unit_changed = state.unit_tracker.calculate_unit_change(new_price)
    print(f"Unit changed: {unit_changed}")
    print(f"Current Unit: {state.unit_tracker.current_unit}")
    print(f"Peak Unit: {state.unit_tracker.peak_unit}")
    print()
    
    # Test the ADVANCE phase logic
    print("Testing ADVANCE phase fragment calculation:")
    
    # Check if current unit equals peak unit and > 0 (new peak condition)
    if state.unit_tracker.current_unit == state.unit_tracker.peak_unit and state.unit_tracker.current_unit > 0:
        if state.position_fragment_usd == Decimal("0"):
            print("[OK] NEW PEAK DETECTED - Calculating fragment")
            state.calculate_position_fragment_at_peak(new_price)
            print(f"  Fragment USD: ${state.position_fragment_usd}")
            print(f"  Fragment ETH: {state.position_fragment_eth:.6f}")
        else:
            print("Fragment already locked for this peak")
    else:
        print("[ERROR] New peak NOT detected")
        print(f"  Condition: current_unit ({state.unit_tracker.current_unit}) == peak_unit ({state.unit_tracker.peak_unit}) and > 0")
    
    print()
    
    # Now simulate price dropping to trigger RETRACEMENT
    retracement_price = entry_price  # Back to entry price (-1 unit from peak)
    print(f"Price drops back to: ${retracement_price} (-1 unit from peak)")
    
    unit_changed = state.unit_tracker.calculate_unit_change(retracement_price) 
    units_from_peak = state.unit_tracker.get_units_from_peak()
    
    print(f"Units from peak: {units_from_peak}")
    
    if units_from_peak <= -1:
        print("[OK] RETRACEMENT trigger detected")
        if state.position_fragment_usd > Decimal("0"):
            print(f"  Fragment available: ${state.position_fragment_usd}")
            print(f"  ETH to sell (-1 unit): {state.position_fragment_eth:.6f} ETH")
            print("[OK] Would execute RETRACEMENT action successfully")
        else:
            print("[ERROR] No fragment available - would fail with zero size error")
    
    print("=" * 60)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_advance_phase_logic())
