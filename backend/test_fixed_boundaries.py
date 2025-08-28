#!/usr/bin/env python3
"""
Test the CORRECTED unit tracking with fixed boundaries
"""
import sys
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.models import UnitTracker

def test_fixed_boundaries():
    """Test that unit boundaries work as intended"""
    
    print("=" * 70)
    print("TESTING CORRECTED UNIT TRACKING - FIXED BOUNDARIES")
    print("=" * 70)
    
    # Create tracker with $5 unit value
    tracker = UnitTracker(unit_value=Decimal("5.0"))
    
    print("Test Scenario: Entry $4500, Unit size $5")
    print("Expected boundaries:")
    print("  Unit  0: $4500 (entry)")
    print("  Unit +1: $4505 (up boundary)")  
    print("  Unit -1: $4495 (down boundary)")
    print()
    
    # Test sequence
    test_prices = [
        (Decimal("4500.00"), "Entry price", 0),
        (Decimal("4502.00"), "Small move up (stay Unit 0)", 0),
        (Decimal("4504.99"), "Just below +1 boundary (stay Unit 0)", 0), 
        (Decimal("4505.00"), "Hit +1 boundary (go to Unit 1)", 1),
        (Decimal("4503.00"), "Drop back but stay Unit 1", 1),
        (Decimal("4507.00"), "Move higher in Unit 1", 1),
        (Decimal("4510.00"), "Hit +2 boundary (go to Unit 2)", 2),
        (Decimal("4508.00"), "Drop back but stay Unit 2", 2),
        (Decimal("4504.99"), "Drop to Unit 1 boundary", 1),
        (Decimal("4495.00"), "Drop to -1 boundary", -1),
        (Decimal("4493.00"), "Drop further in Unit -1", -1),
        (Decimal("4490.00"), "Drop to Unit -2", -2),
    ]
    
    print("TESTING SEQUENCE:")
    print("-" * 70)
    
    for price, description, expected_unit in test_prices:
        unit_changed = tracker.calculate_unit_change(price)
        actual_unit = tracker.current_unit
        
        status = "✅ PASS" if actual_unit == expected_unit else "❌ FAIL"
        change_indicator = " (CHANGED)" if unit_changed else ""
        
        print(f"${price:.2f} | {description:35} | Expected: {expected_unit:2} | Actual: {actual_unit:2} | {status}{change_indicator}")
        
        if actual_unit != expected_unit:
            print(f"  ❌ ERROR: Expected unit {expected_unit}, got {actual_unit}")
            
    print()
    print("BOUNDARY VERIFICATION:")
    boundaries = tracker.get_current_unit_boundaries()
    print(f"Current Unit: {tracker.current_unit}")
    print(f"Next Up Boundary: ${boundaries['next_up']:.2f}")
    print(f"Next Down Boundary: ${boundaries['next_down']:.2f}")
    
    print()
    print("UNIT BOUNDARIES STORED:")
    for unit, price in sorted(tracker.unit_boundaries.items()):
        print(f"  Unit {unit:2}: ${price:.2f}")
    
    print()
    print("=" * 70)
    print("KEY INSIGHT: Price can fluctuate within unit without triggering changes!")
    print("Only crossing EXACT boundaries ($4505, $4495, etc) triggers unit changes!")
    print("=" * 70)

if __name__ == "__main__":
    test_fixed_boundaries()
