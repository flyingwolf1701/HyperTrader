"""
Test script to verify all new module imports work correctly
"""

import sys
import os

# Add src directory to path
src_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, src_dir)

def test_imports():
    """Test that all new modules import correctly"""
    print("Testing module imports...")
    
    try:
        # Test data_models import
        print("1. Testing data_models...")
        from strategy.data_models import (
            OrderType, Phase, ExecutionStatus, PositionState, 
            WindowState, PositionConfig, UnitChangeEvent, 
            OrderFillEvent, CompoundGrowthMetrics
        )
        print("   [OK] data_models imported successfully")
        
        # Test strategy_engine import
        print("2. Testing strategy_engine...")
        from strategy.strategy_engine import LongWalletStrategy
        print("   [OK] strategy_engine imported successfully")
        
        # Test order_manager import
        print("3. Testing order_manager...")
        from strategy.order_manager import OrderManager
        print("   [OK] order_manager imported successfully")
        
        # Test position_tracker import
        print("4. Testing position_tracker...")
        from strategy.position_tracker import PositionTracker
        print("   [OK] position_tracker imported successfully")
        
        # Test updated position_map import
        print("5. Testing position_map...")
        from strategy.position_map import (
            calculate_initial_position_map,
            add_unit_level,
            get_active_orders,
            get_filled_orders
        )
        print("   [OK] position_map imported successfully")
        
        # Test updated unit_tracker import
        print("6. Testing unit_tracker...")
        from strategy.unit_tracker import UnitTracker
        print("   [OK] unit_tracker imported successfully")
        
        print("\n[SUCCESS] All imports successful!")
        return True
        
    except ImportError as e:
        print(f"\n[ERROR] Import error: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        return False


def test_basic_functionality():
    """Test basic functionality of new modules"""
    print("\nTesting basic functionality...")
    
    try:
        from decimal import Decimal
        from strategy.data_models import PositionState, Phase
        from strategy.strategy_engine import LongWalletStrategy
        from strategy.position_tracker import PositionTracker
        
        # Create a position state
        position_state = PositionState(
            entry_price=Decimal("100"),
            unit_size_usd=Decimal("10"),
            asset_size=Decimal("1"),
            position_value_usd=Decimal("100"),
            original_asset_size=Decimal("1"),
            original_position_value_usd=Decimal("100"),
            long_fragment_asset=Decimal("0.25"),
            long_fragment_usd=Decimal("25")
        )
        print("   [OK] PositionState created")
        
        # Create strategy engine
        strategy = LongWalletStrategy(position_state)
        print("   [OK] LongWalletStrategy created")
        print(f"     Initial phase: {strategy.current_phase.value}")
        print(f"     Initial windows: {strategy.windows.stop_loss_orders}")
        
        # Create position tracker
        tracker = PositionTracker(position_state, Decimal("10"))
        print("   [OK] PositionTracker created")
        print(f"     Current unit: {tracker.current_unit}")
        
        print("\n[SUCCESS] Basic functionality test passed!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("HyperTrader Module Import Test")
    print("=" * 50)
    
    imports_ok = test_imports()
    
    if imports_ok:
        functionality_ok = test_basic_functionality()
        
        if functionality_ok:
            print("\n" + "=" * 50)
            print("[SUCCESS] ALL TESTS PASSED!")
            print("=" * 50)
        else:
            print("\n" + "=" * 50)
            print("[WARNING] Imports OK but functionality tests failed")
            print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("[ERROR] Import tests failed")
        print("=" * 50)