"""Test script to verify the fixes"""

import sys
import os
src_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, src_dir)

def test_imports():
    """Test that imports work correctly"""
    print("Testing imports after fix...")
    
    try:
        # Test importing from strategy package
        from strategy import OrderType, Phase
        print(f"[OK] OrderType imported: {[e.name for e in OrderType]}")
        print(f"[OK] Phase imported: {[e.name for e in Phase]}")
        
        # Test that STOP_LOSS_SELL exists
        assert hasattr(OrderType, 'STOP_LOSS_SELL'), "STOP_LOSS_SELL missing"
        print("[OK] STOP_LOSS_SELL exists")
        
        # Test that LIMIT_SELL does NOT exist
        assert not hasattr(OrderType, 'LIMIT_SELL'), "LIMIT_SELL should not exist"
        print("[OK] LIMIT_SELL correctly removed")
        
        # Test importing position map functions
        from strategy import calculate_initial_position_map
        print("[OK] calculate_initial_position_map imported")
        
        # Test importing UnitTracker for backward compatibility
        from strategy import UnitTracker
        print("[OK] UnitTracker imported (backward compatibility)")
        
        print("\n[SUCCESS] All imports working correctly!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_order_type_usage():
    """Test that OrderType can be used correctly"""
    print("\nTesting OrderType usage...")
    
    try:
        from strategy import OrderType
        
        # Test creating order type
        order_type = OrderType.STOP_LOSS_SELL
        print(f"[OK] Created order type: {order_type.value}")
        
        # Test comparison
        assert order_type == OrderType.STOP_LOSS_SELL
        assert order_type != OrderType.LIMIT_BUY
        print("[OK] Order type comparison works")
        
        print("\n[SUCCESS] OrderType usage test passed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] OrderType usage test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Testing fixes for main.py")
    print("=" * 50)
    
    import_ok = test_imports()
    usage_ok = test_order_type_usage()
    
    if import_ok and usage_ok:
        print("\n" + "=" * 50)
        print("[SUCCESS] All tests passed! The fix is working.")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("[ERROR] Some tests failed.")
        print("=" * 50)