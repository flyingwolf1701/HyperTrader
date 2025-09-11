#!/usr/bin/env python3
"""
SOL Trading Strategy Test Runner
Simple script to generate mock data and run complete system test

Usage:
    python run_sol_test.py [--generate-only] [--test-only] [--speed SPEED]
"""

import argparse
import asyncio
import sys
from pathlib import Path


def generate_mock_data() -> str:
    """Generate SOL mock data"""
    print("📝 Generating SOL mock data...")
    
    # Import and run generator
    exec("""
from sol_mock_data_generator import SOLMockDataGenerator

generator = SOLMockDataGenerator()
messages = generator.generate_complete_cycle()
filename = generator.save_mock_data(messages)
""", globals())
    
    return "sol_mock_data.json"


async def run_system_test(playback_speed: float = 1.0) -> bool:
    """Run complete system test"""
    print(f"🧪 Running trading system test (speed: {playback_speed}x)...")
    
    # Import and run test
    exec("""
from trading_system_test import TradingSystemTester

async def run_test():
    tester = TradingSystemTester()
    if hasattr(tester, 'mock_ws') and tester.mock_ws:
        tester.mock_ws.set_playback_speed(playback_speed)
    return await tester.run_complete_test()

result = await run_test()
""", globals(), {"playback_speed": playback_speed})
    
    return globals().get('result', False)


def main():
    """Main runner"""
    parser = argparse.ArgumentParser(description="SOL Trading Strategy Test Runner")
    parser.add_argument("--generate-only", action="store_true", help="Only generate mock data")
    parser.add_argument("--test-only", action="store_true", help="Only run tests (assume data exists)")
    parser.add_argument("--speed", type=float, default=2.0, help="Playback speed multiplier (default: 2.0)")
    
    args = parser.parse_args()
    
    print("🚀 SOL Trading Strategy Test Suite")
    print("=" * 40)
    print(f"Parameters from your command:")
    print(f"  Symbol: SOL")
    print(f"  Position size: $2000")
    print(f"  Leverage: 20x")
    print(f"  Unit size: $0.1")
    print(f"  Wallet: long")
    print("=" * 40)
    
    try:
        if args.generate_only:
            # Generate mock data only
            filename = generate_mock_data()
            print(f"✅ Mock data generated: {filename}")
            print("📋 Use --test-only to run tests with this data")
            
        elif args.test_only:
            # Run tests only
            if not Path("sol_mock_data.json").exists():
                print("❌ Mock data file not found. Run without --test-only first.")
                return False
            
            success = asyncio.run(run_system_test(args.speed))
            if success:
                print("✅ All tests passed!")
            else:
                print("❌ Tests failed!")
            return success
            
        else:
            # Full run: generate data then test
            filename = generate_mock_data()
            print(f"✅ Mock data generated: {filename}")
            
            print("\n" + "=" * 40)
            success = asyncio.run(run_system_test(args.speed))
            
            if success:
                print("\n🎉 Complete test suite passed!")
                print("📊 Your SOL trading strategy implementation appears to be working correctly")
                print("\n🎯 Next steps:")
                print("  1. Review the test report above")
                print("  2. Verify fragment sizes remain consistent")
                print("  3. Check phase transitions occur correctly")
                print("  4. Test with real data when ready")
            else:
                print("\n❌ Test suite failed!")
                print("🔍 Check the logs above for specific issues")
            
            return success
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
