"""
Test to verify all fixes work correctly
"""

import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from src.core.websocket_client_fixed import FixedHyperliquidWebSocketClient
from src.core.models import UnitTracker

async def test_websocket_fixes():
    """Test that WebSocket doesn't process historical data"""
    print("=" * 60)
    print("TESTING WEBSOCKET FIXES")
    print("=" * 60)
    
    # Create fixed client
    client = FixedHyperliquidWebSocketClient(testnet=True)
    
    # Track callback calls
    callback_count = 0
    callback_times = []
    
    async def price_callback(price):
        nonlocal callback_count, callback_times
        callback_count += 1
        callback_times.append(datetime.now())
        print(f"Callback #{callback_count} at price ${price}")
    
    # Connect
    connected = await client.connect()
    if not connected:
        print("Failed to connect")
        return
    
    print("Connected successfully")
    print("Grace period active - ignoring historical trades...")
    
    # Subscribe
    tracker = UnitTracker(unit_value=Decimal("50"))  # Use reasonable unit value
    await client.subscribe_to_trades("ETH", Decimal("50"), tracker, price_callback)
    
    # Listen for 10 seconds
    listen_task = asyncio.create_task(client.listen())
    await asyncio.sleep(10)
    
    # Check results
    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    print(f"Total callbacks: {callback_count}")
    
    if callback_count > 0:
        # Check timing between callbacks
        for i in range(1, len(callback_times)):
            time_diff = (callback_times[i] - callback_times[i-1]).total_seconds()
            print(f"Time between callback {i} and {i+1}: {time_diff:.1f}s")
            if time_diff < 5:
                print("  WARNING: Callbacks too close together!")
    
    # Cleanup
    await client.disconnect()
    listen_task.cancel()
    
    print("\nTest complete")

def test_unit_value_validation():
    """Test unit value validation"""
    print("\n" + "=" * 60)
    print("TESTING UNIT VALUE VALIDATION")
    print("=" * 60)
    
    eth_price = Decimal("4500")
    
    # Test various unit values
    test_values = [
        (Decimal("5"), "Too small - 0.11% moves"),
        (Decimal("25"), "Borderline - 0.56% moves"),
        (Decimal("50"), "Reasonable - 1.11% moves"),
        (Decimal("100"), "Good - 2.22% moves"),
        (Decimal("200"), "Conservative - 4.44% moves")
    ]
    
    for unit_value, description in test_values:
        percentage = (unit_value / eth_price) * 100
        print(f"Unit value ${unit_value}: {percentage:.2f}% - {description}")
        
        if percentage < 0.5:
            print("  [X] TOO SMALL - Will cause rapid trading!")
        elif percentage < 1.0:
            print("  [!] Small - May trade frequently")
        else:
            print("  [OK] Good size")

async def main():
    """Run all tests"""
    test_unit_value_validation()
    await test_websocket_fixes()

if __name__ == "__main__":
    asyncio.run(main())