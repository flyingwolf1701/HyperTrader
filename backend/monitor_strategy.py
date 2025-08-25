#!/usr/bin/env python3
"""Monitor the live strategy and display status"""

import asyncio
import json
import time
from datetime import datetime

async def monitor():
    while True:
        try:
            # Read strategy state
            with open("strategy_state.json", "r") as f:
                state = json.load(f)
            
            # Display current status
            print(f"\n{'='*60}")
            print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
            print(f"Symbol: {state['symbol']}")
            print(f"Phase: {state['phase']}")
            print(f"Entry Price: ${state['entry_price']:.4f}")
            print(f"Last Price: ${state['last_price']:.4f}")
            print(f"Current Unit: {state['current_unit']}")
            print(f"Peak Unit: {state['peak_unit']}")
            
            # Calculate price change
            price_change = state['last_price'] - state['entry_price']
            price_change_pct = (price_change / state['entry_price']) * 100
            print(f"Price Change: ${price_change:.4f} ({price_change_pct:+.2f}%)")
            
            # Position info
            print(f"\nPositions:")
            print(f"  Long: ${state['current_long_position']:.2f}")
            print(f"  Short: ${state['current_short_position']:.2f}")
            print(f"  Cash: ${state['current_cash_position']:.2f}")
            
            # Fragment info
            if state['position_fragment']:
                print(f"  Position Fragment: ${state['position_fragment']:.2f}")
            if state['hedge_fragment']:
                print(f"  Hedge Fragment: ${state['hedge_fragment']:.2f}")
            
            # Phase-specific info
            if state['phase'] == 'ADVANCE' and state['peak_unit'] > 0:
                print(f"\n⬆️ At peak unit {state['peak_unit']}")
            elif state['phase'] == 'RETRACEMENT':
                units_from_peak = state['peak_unit'] - state['current_unit']
                print(f"\n⬇️ RETRACEMENT: {units_from_peak} units from peak")
            elif state['phase'] == 'DECLINE':
                print(f"\n📉 DECLINE: Valley at {state['valley_unit']}")
            elif state['phase'] == 'RECOVERY':
                units_from_valley = state['current_unit'] - state['valley_unit']
                print(f"\n📈 RECOVERY: {units_from_valley} units from valley")
                
        except FileNotFoundError:
            print("No strategy running")
        except Exception as e:
            print(f"Error: {e}")
        
        # Wait 5 seconds before next update
        await asyncio.sleep(5)

if __name__ == "__main__":
    print("Starting Strategy Monitor...")
    print("Press Ctrl+C to stop")
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print("\nMonitor stopped")