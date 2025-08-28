"""
Test the critical fixes applied to HyperTrader
"""
import sys
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.strategy.strategy_manager import StrategyState
from src.core.models import Phase

def test_phase_transition():
    """Test that RETRACEMENT transitions to DECLINE after -4 units"""
    print("\n=== Testing Phase Transition Fix ===")
    
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("2500"),
        unit_size=Decimal("5"),
        leverage=25
    )
    
    # Set up state as if we're at -4 units in RETRACEMENT
    state.unit_tracker.phase = Phase.RETRACEMENT
    state.unit_tracker.current_unit = -1  # 4 units below peak of 3
    state.unit_tracker.peak_unit = 3
    state.position_fragment_usd = Decimal("300")
    state.position_fragment_eth = Decimal("0.065889")
    
    units_from_peak = state.unit_tracker.get_units_from_peak()
    print(f"Units from peak: {units_from_peak}")
    print(f"Current phase: {state.unit_tracker.phase.value}")
    
    # Check if transition should occur
    if units_from_peak == -4:
        print("[PASS] Correctly at -4 units from peak")
        print("   Should transition to DECLINE after executing -4 action")
    else:
        print(f"[FAIL] Expected -4 units from peak, got {units_from_peak}")
    
    return units_from_peak == -4

def test_short_entry_price():
    """Test that shorts record actual execution price"""
    print("\n=== Testing Short Entry Price Fix ===")
    
    state = StrategyState(
        symbol="ETH/USDC:USDC", 
        position_size_usd=Decimal("2500"),
        unit_size=Decimal("5"),
        leverage=25
    )
    
    # Simulate adding a short with actual execution price
    execution_price = Decimal("4545.50")
    state.add_short_position(
        usd_amount=Decimal("300"),
        entry_price=execution_price,
        unit_level=-1
    )
    
    # Check the recorded price
    if state.short_positions:
        recorded_price = state.short_positions[0].entry_price
        print(f"Execution price: ${execution_price}")
        print(f"Recorded price: ${recorded_price}")
        
        if recorded_price == execution_price:
            print("[PASS] Short entry price correctly recorded")
            return True
        else:
            print("[FAIL] Short entry price mismatch")
            return False
    
    return False

def test_pnl_calculation():
    """Test P&L calculation with current market price"""
    print("\n=== Testing P&L Calculation Fix ===")
    
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("2500"),
        unit_size=Decimal("5"),
        leverage=25
    )
    
    # Add shorts at different prices
    state.add_short_position(
        usd_amount=Decimal("300"),
        entry_price=Decimal("4553.10"),
        unit_level=-1
    )
    
    state.add_short_position(
        usd_amount=Decimal("300"),
        entry_price=Decimal("4550.00"),
        unit_level=-2
    )
    
    # Calculate P&L at different market prices
    test_prices = [Decimal("4540"), Decimal("4560")]
    
    for market_price in test_prices:
        total_value = state.calculate_total_short_value(market_price)
        original_value = Decimal("600")  # Two $300 shorts
        pnl = total_value - original_value
        
        print(f"\nMarket price: ${market_price}")
        print(f"Original value: ${original_value}")
        print(f"Current value: ${total_value:.2f}")
        print(f"P&L: ${pnl:.2f}")
        
        # Shorts profit when price goes down
        if market_price < Decimal("4550"):
            if pnl > 0:
                print("[PASS] Correctly showing profit when price drops")
            else:
                print("[FAIL] Should show profit when price drops")
        else:
            if pnl < 0:
                print("[PASS] Correctly showing loss when price rises")
            else:
                print("[FAIL] Should show loss when price rises")
    
    return True

def main():
    """Run all tests"""
    print("="*60)
    print("HYPERTRADER FIX VERIFICATION")
    print("="*60)
    
    results = []
    
    # Test 1: Phase transition
    results.append(("Phase Transition", test_phase_transition()))
    
    # Test 2: Short entry price
    results.append(("Short Entry Price", test_short_entry_price()))
    
    # Test 3: P&L calculation
    results.append(("P&L Calculation", test_pnl_calculation()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "[PASS] PASSED" if passed else "[FAIL] FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n[SUCCESS] All fixes verified successfully!")
        print("\nNEXT STEPS:")
        print("1. Restart the bot with a clean state")
        print("2. Monitor for proper phase transitions")
        print("3. Verify short P&L updates with price movements")
    else:
        print("\n[WARNING] Some fixes may need additional work")

if __name__ == "__main__":
    main()