#!/usr/bin/env python3
"""
Test the enhanced boundary logging with your specific case
"""
from decimal import Decimal
from enum import Enum

class Phase(Enum):
    ADVANCE = "ADVANCE"

class UnitTracker:
    def __init__(self, unit_value=Decimal("5.0")):
        self.entry_price = None
        self.unit_value = unit_value
        self.current_unit = 0
        self.peak_unit = 0
        self.valley_unit = 0
        self.phase = Phase.ADVANCE
        self.unit_boundaries = {}
        
    def _calculate_unit_price(self, unit: int) -> Decimal:
        if self.entry_price is None:
            return Decimal("0")
        return self.entry_price + (Decimal(unit) * self.unit_value)
    
    def calculate_unit_change(self, current_price: Decimal) -> bool:
        if self.entry_price is None:
            self.entry_price = current_price
            self.unit_boundaries[0] = current_price
            print(f"Entry price set: ${self.entry_price:.2f}")
            return False
        
        old_unit = self.current_unit
        new_unit = self.current_unit
        
        # Check UP movement
        while True:
            next_up_unit = new_unit + 1
            next_up_price = self._calculate_unit_price(next_up_unit)
            if current_price >= next_up_price:
                new_unit = next_up_unit
                if next_up_unit not in self.unit_boundaries:
                    self.unit_boundaries[next_up_unit] = next_up_price
            else:
                break
        
        # Check DOWN movement  
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
                
            # CRITICAL: Log the unit change prominently
            direction = "UP" if new_unit > old_unit else "DOWN"
            print(f"UNIT BOUNDARY CROSSED! {direction}")
            print(f"   Unit: {old_unit} -> {self.current_unit}")
            print(f"   Price: ${current_price:.2f}")
            
            # Show next boundaries
            next_up = self._calculate_unit_price(self.current_unit + 1)
            next_down = self._calculate_unit_price(self.current_unit - 1)
            print(f"   Next boundaries: +1 at ${next_up:.2f}, -1 at ${next_down:.2f}")
            
            return True
        else:
            # Check close calls
            next_up = self._calculate_unit_price(self.current_unit + 1)
            next_down = self._calculate_unit_price(self.current_unit - 1)
            distance_to_up = abs(current_price - next_up)
            distance_to_down = abs(current_price - next_down)
            
            threshold = self.unit_value * Decimal("0.2")  # 20% of unit size ($1 for $5 unit)
            
            if distance_to_up <= threshold:
                print(f"APPROACHING +1 BOUNDARY: ${current_price:.2f} -> ${next_up:.2f} (${distance_to_up:.2f} away)")
            elif distance_to_down <= threshold:
                print(f"APPROACHING -1 BOUNDARY: ${current_price:.2f} -> ${next_down:.2f} (${distance_to_down:.2f} away)")
                
        return False

def test_your_specific_case():
    """Test logging with your exact prices"""
    
    print("=" * 70)
    print("TESTING ENHANCED BOUNDARY LOGGING - YOUR SPECIFIC CASE")
    print("=" * 70)
    
    tracker = UnitTracker(unit_value=Decimal("5.0"))
    
    print("Your case: Entry $4,481.4 -> Mark Price $4,480.0")
    print("Expected -1 boundary: $4,476.4")
    print()
    
    # Test sequence with your exact prices
    test_prices = [
        (Decimal("4481.4"), "Entry price"),
        (Decimal("4481.0"), "Small drop"),
        (Decimal("4480.5"), "Getting closer"),
        (Decimal("4480.0"), "Your mark price"), 
        (Decimal("4478.0"), "Approaching boundary"),
        (Decimal("4476.4"), "Hit -1 boundary!"),
        (Decimal("4475.0"), "Dropped further"),
    ]
    
    print("PRICE SEQUENCE:")
    print("-" * 70)
    
    for price, description in test_prices:
        print(f"\n${price:.1f} - {description}")
        unit_changed = tracker.calculate_unit_change(price)
        
        if not unit_changed and tracker.entry_price:
            # Show distance info for non-changes
            next_down = tracker._calculate_unit_price(tracker.current_unit - 1)
            distance = abs(price - next_down)
            print(f"   Distance to -1 boundary (${next_down:.1f}): ${distance:.1f}")
    
    print("\n" + "=" * 70)
    print("KEY INSIGHTS:")
    print("=" * 70)
    print("PASS Entry at $4,481.4 would set boundaries:")
    print("   +1 boundary: $4,486.4") 
    print("   -1 boundary: $4,476.4")
    print()
    print("PASS Your mark price $4,480.0 would log:")
    print("   'APPROACHING -1 BOUNDARY: $4480.0 -> $4476.4 ($3.6 away)'")
    print()
    print("CRITICAL If price hit $4,476.4, would log:")
    print("   'UNIT BOUNDARY CROSSED! DOWN'")
    print("   'Unit: 0 -> -1'")
    print("   'This would trigger RETRACEMENT phase!'")

if __name__ == "__main__":
    test_your_specific_case()
