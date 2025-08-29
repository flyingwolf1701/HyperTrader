"""
Test script to validate Patrick's requested changes
"""

from decimal import Decimal
from src.core.models import UnitTracker, Phase
from src.strategy.strategy_manager import StrategyState

def test_unit_tracker_changes():
    """Test that UnitTracker has been updated correctly"""
    print("Testing UnitTracker changes...")
    
    # Test unit_value instead of unit_size
    tracker = UnitTracker(unit_value=Decimal("25.0"))
    assert hasattr(tracker, 'unit_value'), "unit_value attribute missing"
    assert not hasattr(tracker, 'unit_size'), "unit_size should be renamed to unit_value"
    assert tracker.unit_value == Decimal("25.0"), "unit_value not set correctly"
    
    # Test fragment dicts
    assert isinstance(tracker.position_fragment, dict), "position_fragment should be a dict"
    assert isinstance(tracker.hedge_fragment, dict), "hedge_fragment should be a dict"
    assert "usd" in tracker.position_fragment, "position_fragment missing 'usd' key"
    assert "coin_value" in tracker.position_fragment, "position_fragment missing 'coin_value' key"
    
    # Test no debouncing variables
    assert not hasattr(tracker, 'debounce_seconds'), "debounce_seconds should be removed"
    assert not hasattr(tracker, 'pending_unit'), "pending_unit should be removed"
    assert not hasattr(tracker, 'pending_unit_time'), "pending_unit_time should be removed"
    assert not hasattr(tracker, 'last_stable_unit'), "last_stable_unit should be removed"
    
    # Test peak/valley price tracking dicts
    assert isinstance(tracker.peak_unit_prices, dict), "peak_unit_prices should be a dict"
    assert isinstance(tracker.valley_unit_prices, dict), "valley_unit_prices should be a dict"
    
    print("[OK] UnitTracker changes validated")

def test_strategy_state_changes():
    """Test that StrategyState has been updated correctly"""
    print("\nTesting StrategyState changes...")
    
    # Test unit_value parameter
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("1000"),
        unit_value=Decimal("25.0")
    )
    
    assert hasattr(state, 'unit_value'), "unit_value attribute missing"
    assert not hasattr(state, 'unit_size'), "unit_size should be renamed to unit_value"
    assert state.unit_value == Decimal("25.0"), "unit_value not set correctly"
    
    # Test fragment dicts
    assert isinstance(state.position_fragment, dict), "position_fragment should be a dict"
    assert isinstance(state.hedge_fragment, dict), "hedge_fragment should be a dict"
    assert "usd" in state.position_fragment, "position_fragment missing 'usd' key"
    assert "coin_value" in state.position_fragment, "position_fragment missing 'coin_value' key"
    
    # Test that old fragment fields are removed
    assert not hasattr(state, 'position_fragment_usd'), "position_fragment_usd should be removed"
    assert not hasattr(state, 'position_fragment_eth'), "position_fragment_eth should be removed"
    
    print("[OK] StrategyState changes validated")

def test_calculate_unit_change_simplified():
    """Test that calculate_unit_change is simplified"""
    print("\nTesting simplified calculate_unit_change...")
    
    tracker = UnitTracker(unit_value=Decimal("25.0"))
    
    # Set entry price
    result = tracker.calculate_unit_change(Decimal("2500.00"))
    assert tracker.entry_price == Decimal("2500.00"), "Entry price not set"
    assert result == False, "Should return False when setting entry price"
    
    # Test unit change detection (no debouncing)
    result = tracker.calculate_unit_change(Decimal("2525.00"))  # +1 unit
    assert result == True, "Should detect unit change immediately"
    assert tracker.current_unit == 1, "Current unit not updated correctly"
    assert tracker.peak_unit == 1, "Peak unit not updated correctly"
    assert 1 in tracker.peak_unit_prices, "Peak price not tracked"
    
    # Test valley tracking in DECLINE phase
    tracker.phase = Phase.DECLINE  # Set to DECLINE phase
    result = tracker.calculate_unit_change(Decimal("2475.00"))  # -1 unit from entry
    assert result == True, "Should detect unit change"
    assert tracker.current_unit == -1, "Current unit not updated correctly"
    assert tracker.valley_unit == -1, "Valley unit not updated in DECLINE phase"
    assert -1 in tracker.valley_unit_prices, "Valley price not tracked"
    
    print("[OK] calculate_unit_change simplified correctly")

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Patrick's requested changes")
    print("=" * 60)
    
    try:
        test_unit_tracker_changes()
        test_strategy_state_changes()
        test_calculate_unit_change_simplified()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] ALL TESTS PASSED - Changes successfully implemented!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n[FAILED] TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())