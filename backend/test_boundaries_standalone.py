#!/usr/bin/env python3
"""
Test the CORRECTED unit tracking with fixed boundaries - STANDALONE
"""
from decimal import Decimal
from enum import Enum

class Phase(Enum):
    ADVANCE = "ADVANCE"
    RETRACEMENT = "RETRACEMENT"
    DECLINE = "DECLINE"
    RECOVERY = "RECOVERY"

class UnitTracker:
    """CORRECTED: Uses fixed unit boundaries, not continuous calculation."""
    
    def __init__(self, unit_value=Decimal("5.0")):
        self.entry_price = None
        self.unit_value = unit_value
        self.current_unit = 0
        self.peak_unit = 0
        self.valley_unit = 0
        self.phase = Phase.ADVANCE
        self.unit_boundaries = {}
        
    def _calculate_unit_price(self, unit: int) -> Decimal:
        """Calculate the exact price for a given unit level"""
        if self.entry_price is None:
            return Decimal("0")
        return self.entry_price + (Decimal(unit) * self.unit_value)
    
    def calculate_unit_change(self, current_price: Decimal) -> bool:
        """Check if price has crossed a FIXED unit boundary."""
        if self.entry_price is None:
            self.entry_price = current_price
            self.unit_boundaries[0] = current_price
            print(f"Entry price set: ${self.entry_price:.2f}")
            return False
        
        old_unit = self.current_unit
        new_unit = self.current_unit
        
        # Check if we need to move UP (positive units)
        while True:
            next_up_unit = new_unit + 1
            next_up_price = self._calculate_unit_price(next_up_unit)
            
            if current_price >= next_up_price:
                new_unit = next_up_unit
                if next_up_unit not in self.unit_boundaries:
                    self.unit_boundaries[next_up_unit] = next_up_price
            else:
                break
        
        # Check if we need to move DOWN (negative units)
        while True:
            next_down_unit = new_unit - 1
            next_down_price = self._calculate_unit_price(next_down_unit)
            
            if current_price <= next_down_price:
                new_unit = next_down_unit
                if next_down_unit not in self.unit_boundaries:
                    self.unit_boundaries[next_down_unit] = next_down_price
            else:
                break
        
        # Update unit if it changed
        if new_unit != old_unit:
            self.current_unit = new_unit
            if self.current_unit > self.peak_unit:
                self.peak_unit = self.current_unit
            return True
        return False

def test_fixed_boundaries():
    """Test that unit boundaries work as intended"""
    
    print("=" * 70)
    print("TESTING CORRECTED UNIT TRACKING - FIXED BOUNDARIES")
    print("=" * 70)
    
    tracker = UnitTracker(unit_value=Decimal("5.0"))
    
    print("Test Scenario: Entry $4500, Unit size $5")
    print("Expected boundaries:")
    print("  Unit  0: $4500 (entry)")
    print("  Unit +1: $4505 (up boundary)")  
    print("  Unit -1: $4495 (down boundary)")
    print()
    
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
    
    all_passed = True
    for price, description, expected_unit in test_prices:
        unit_changed = tracker.calculate_unit_change(price)
        actual_unit = tracker.current_unit
        
        passed = actual_unit == expected_unit
        all_passed = all_passed and passed
        
        status = "PASS" if passed else "FAIL"
        change_indicator = " (CHANGED)" if unit_changed else ""
        
        print(f"${price:.2f} | {description:35} | Expected: {expected_unit:2} | Actual: {actual_unit:2} | {status}{change_indicator}")
        
        if not passed:
            print(f"  ERROR: Expected unit {expected_unit}, got {actual_unit}")
            
    print()
    print("UNIT BOUNDARIES STORED:")
    for unit, price in sorted(tracker.unit_boundaries.items()):
        print(f"  Unit {unit:2}: ${price:.2f}")
    
    print()
    if all_passed:
        print("ALL TESTS PASSED! Fixed boundaries working correctly!")
    else:
        print("SOME TESTS FAILED! Need to debug boundary logic.")
        
    print("=" * 70)
    print("KEY INSIGHT: Price can fluctuate within unit without triggering changes!")
    print("Only crossing EXACT boundaries ($4505, $4495, etc) triggers unit changes!")
    print("=" * 70)

if __name__ == "__main__":
    test_fixed_boundaries()
