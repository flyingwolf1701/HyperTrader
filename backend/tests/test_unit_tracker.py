"""
Tests for Stage 1 & 2: Unit tracking functionality
"""
import pytest
from decimal import Decimal
from src.models import UnitTracker, Phase


class TestUnitTracker:
    """Test cases for UnitTracker class"""
    
    def test_initialization(self):
        """Test UnitTracker initializes with correct defaults"""
        tracker = UnitTracker()
        assert tracker.entry_price is None
        assert tracker.unit_size == Decimal("2.0")
        assert tracker.current_unit == 0
        assert tracker.peak_unit == 0
        assert tracker.valley_unit == 0
        assert tracker.phase == Phase.ADVANCE
        
    def test_custom_unit_size(self):
        """Test UnitTracker with custom unit size"""
        tracker = UnitTracker(unit_size=Decimal("5.0"))
        assert tracker.unit_size == Decimal("5.0")
        
    def test_entry_price_set_on_first_price(self):
        """Test entry price is set on first price received"""
        tracker = UnitTracker()
        assert tracker.entry_price is None
        
        # First price should set entry price
        changed = tracker.calculate_unit_change(Decimal("3450.00"))
        assert not changed  # No unit change on first price
        assert tracker.entry_price == Decimal("3450.00")
        assert tracker.current_unit == 0
        
    def test_upward_unit_change(self):
        """Test unit changes when price moves up"""
        tracker = UnitTracker(entry_price=Decimal("3450.00"), unit_size=Decimal("2.0"))
        
        # Price up by 0.5 units - should not trigger change
        changed = tracker.calculate_unit_change(Decimal("3451.00"))
        assert not changed
        assert tracker.current_unit == 0
        
        # Price up by 1 unit - should trigger change
        changed = tracker.calculate_unit_change(Decimal("3452.00"))
        assert changed
        assert tracker.current_unit == 1
        assert tracker.peak_unit == 1  # Peak should update
        
        # Price up by 3 units
        changed = tracker.calculate_unit_change(Decimal("3456.00"))
        assert changed
        assert tracker.current_unit == 3
        assert tracker.peak_unit == 3
        
    def test_downward_unit_change(self):
        """Test unit changes when price moves down"""
        tracker = UnitTracker(entry_price=Decimal("3450.00"), unit_size=Decimal("2.0"))
        
        # Price down by 1 unit - should not trigger change
        changed = tracker.calculate_unit_change(Decimal("3449.00"))
        assert not changed
        assert tracker.current_unit == 0
        
        # Price down by 2 units - should trigger change
        changed = tracker.calculate_unit_change(Decimal("3446.00"))
        assert changed
        assert tracker.current_unit == -2
        assert tracker.valley_unit == -2  # Valley should update
        
        # Price down by 3 units
        changed = tracker.calculate_unit_change(Decimal("3444.00"))
        assert changed
        assert tracker.current_unit == -3
        assert tracker.valley_unit == -3
        
    def test_peak_tracking(self):
        """Test peak_unit only updates when making new highs"""
        tracker = UnitTracker(entry_price=Decimal("3450.00"), unit_size=Decimal("2.0"))
        
        # Move up to unit 3
        tracker.calculate_unit_change(Decimal("3456.00"))
        assert tracker.current_unit == 3
        assert tracker.peak_unit == 3
        
        # Move down to unit 1
        tracker.calculate_unit_change(Decimal("3452.00"))
        assert tracker.current_unit == 1
        assert tracker.peak_unit == 3  # Peak should remain at 3
        
        # Move up to unit 2
        tracker.calculate_unit_change(Decimal("3454.00"))
        assert tracker.current_unit == 2
        assert tracker.peak_unit == 3  # Peak should still be 3
        
        # Move up to unit 4 (new high)
        tracker.calculate_unit_change(Decimal("3458.00"))
        assert tracker.current_unit == 4
        assert tracker.peak_unit == 4  # Peak should update
        
    def test_valley_tracking(self):
        """Test valley_unit only updates when making new lows"""
        tracker = UnitTracker(entry_price=Decimal("3450.00"), unit_size=Decimal("2.0"))
        
        # Move down to unit -3
        tracker.calculate_unit_change(Decimal("3444.00"))
        assert tracker.current_unit == -3
        assert tracker.valley_unit == -3
        
        # Move up to unit -1
        tracker.calculate_unit_change(Decimal("3448.00"))
        assert tracker.current_unit == -1
        assert tracker.valley_unit == -3  # Valley should remain at -3
        
        # Move down to unit -2
        tracker.calculate_unit_change(Decimal("3446.00"))
        assert tracker.current_unit == -2
        assert tracker.valley_unit == -3  # Valley should still be -3
        
        # Move down to unit -4 (new low)
        tracker.calculate_unit_change(Decimal("3442.00"))
        assert tracker.current_unit == -4
        assert tracker.valley_unit == -4  # Valley should update
        
    def test_units_from_peak(self):
        """Test calculation of units from peak"""
        tracker = UnitTracker(entry_price=Decimal("3450.00"), unit_size=Decimal("2.0"))
        
        # Move up to peak of 3
        tracker.calculate_unit_change(Decimal("3456.00"))
        assert tracker.get_units_from_peak() == 0  # At peak
        
        # Move down to unit 1
        tracker.calculate_unit_change(Decimal("3452.00"))
        assert tracker.get_units_from_peak() == -2  # 2 units below peak
        
        # Move down to unit -1
        tracker.calculate_unit_change(Decimal("3448.00"))
        assert tracker.get_units_from_peak() == -4  # 4 units below peak
        
    def test_units_from_valley(self):
        """Test calculation of units from valley"""
        tracker = UnitTracker(entry_price=Decimal("3450.00"), unit_size=Decimal("2.0"))
        
        # Move down to valley of -3
        tracker.calculate_unit_change(Decimal("3444.00"))
        assert tracker.get_units_from_valley() == 0  # At valley
        
        # Move up to unit -1
        tracker.calculate_unit_change(Decimal("3448.00"))
        assert tracker.get_units_from_valley() == 2  # 2 units above valley
        
        # Move up to unit 1
        tracker.calculate_unit_change(Decimal("3452.00"))
        assert tracker.get_units_from_valley() == 4  # 4 units above valley
        
    def test_decimal_precision(self):
        """Test that Decimal handles small crypto prices correctly"""
        tracker = UnitTracker(entry_price=Decimal("0.00012345"), unit_size=Decimal("0.00000100"))
        
        # Test small price movements
        changed = tracker.calculate_unit_change(Decimal("0.00012445"))
        assert changed
        assert tracker.current_unit == 1
        
        changed = tracker.calculate_unit_change(Decimal("0.00012545"))
        assert changed
        assert tracker.current_unit == 2
        
        # Test negative movement
        changed = tracker.calculate_unit_change(Decimal("0.00012145"))
        assert changed
        assert tracker.current_unit == -2