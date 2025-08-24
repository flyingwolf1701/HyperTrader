#!/usr/bin/env python3
"""
Test script for WebSocket-powered strategy monitoring
"""
import asyncio
import json
import os
from app.services.strategy_monitor import strategy_monitor
from app.api.simple import StrategyState, save_strategy_state, load_strategy_state

async def test_websocket_strategy():
    """Test the WebSocket strategy monitoring system"""
    print("🧪 Testing WebSocket Strategy Monitor")
    
    # Create a test strategy state
    test_state = StrategyState(
        symbol="PURR/USDC:USDC",
        unit_size=0.1,
        entry_price=5.12,
        current_unit=0,
        peak_unit=0,
        valley_unit=None,
        phase="ADVANCE",
        long_invested=50.0,
        long_cash=0.0,
        hedge_short=0.0,
        last_price=5.12,
        position_size_usd=50.0
    )
    
    # Save test state
    save_strategy_state(test_state)
    print("✅ Test strategy state created")
    
    # Verify state was saved
    loaded_state = load_strategy_state()
    if loaded_state:
        print(f"✅ Strategy state loaded: {loaded_state.symbol} at ${loaded_state.entry_price}")
    else:
        print("❌ Failed to load strategy state")
        return
    
    # Start WebSocket monitoring
    print("🚀 Starting WebSocket monitoring...")
    await strategy_monitor.start_monitoring()
    
    # Let it run for 30 seconds to test real-time updates
    print("⏰ Monitoring for 30 seconds...")
    await asyncio.sleep(30)
    
    # Stop monitoring
    print("🛑 Stopping WebSocket monitoring...")
    await strategy_monitor.stop_monitoring()
    
    # Check final state
    final_state = load_strategy_state()
    if final_state:
        print(f"✅ Final state: Phase={final_state.phase}, Last Price=${final_state.last_price}")
    
    # Cleanup
    if os.path.exists("strategy_state.json"):
        os.remove("strategy_state.json")
        print("🧹 Cleanup complete")

if __name__ == "__main__":
    asyncio.run(test_websocket_strategy())