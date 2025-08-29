#!/usr/bin/env python3
"""
Test Fragment Calculation Logic
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.strategy.strategy_manager import StrategyState

def test_fragment_calculation():
    """Test that fragment calculation works correctly"""
    
    print("Testing Fragment Calculation Logic")
    print("=" * 50)
    
    # Create strategy state
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("2500"),
        unit_size=Decimal("5"),
        leverage=25
    )
    
    print(f"Initial state:")
    print(f"  Position Size: ${state.position_size_usd}")
    print(f"  Fragment USD: ${state.position_fragment_usd}")
    print(f"  Fragment ETH: {state.position_fragment_eth}")
    print()
    
    # Test fragment calculation at peak
    peak_price = Decimal("4580")
    print(f"Calculating fragment at peak price: ${peak_price}")
    
    state.calculate_position_fragment_at_peak(peak_price)
    
    print(f"After fragment calculation:")
    print(f"  Fragment USD: ${state.position_fragment_usd}")
    print(f"  Fragment ETH: {state.position_fragment_eth:.6f}")
    print(f"  Expected USD: ${state.position_size_usd * Decimal('0.12')}")
    print(f"  Expected ETH: {(state.position_size_usd * Decimal('0.12') / peak_price):.6f}")
    print()
    
    # Verify calculations
    expected_usd = state.position_size_usd * Decimal("0.12")
    expected_eth = expected_usd / peak_price
    
    if state.position_fragment_usd == expected_usd:
        print("✅ Fragment USD calculation CORRECT")
    else:
        print(f"❌ Fragment USD calculation WRONG: got {state.position_fragment_usd}, expected {expected_usd}")
    
    if abs(state.position_fragment_eth - expected_eth) < Decimal("0.000001"):
        print("✅ Fragment ETH calculation CORRECT")
    else:
        print(f"❌ Fragment ETH calculation WRONG: got {state.position_fragment_eth}, expected {expected_eth}")

if __name__ == "__main__":
    test_fragment_calculation()
