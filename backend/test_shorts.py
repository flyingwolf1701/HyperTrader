#!/usr/bin/env python3
"""Test short positions by forcing a large price drop"""

import json
import os

# Load current state
with open("strategy_state.json", "r") as f:
    state = json.load(f)

print(f"Current state: Unit {state['current_unit']}, Peak {state['peak_unit']}, Phase {state['phase']}")
print(f"Current position: ${state['current_long_position']}")

# Force a large drop - 5 units below peak
new_unit = state['peak_unit'] - 5  
state['current_unit'] = new_unit
state['last_price'] = state['entry_price'] - (5 * state['unit_size'])  # Drop by 5 units

# Save modified state
with open("strategy_state.json", "w") as f:
    json.dump(state, f, indent=2)

print(f"\nForced drop to unit {new_unit} (5 units below peak)")
print(f"New price: ${state['last_price']}")
print("Now run update to trigger short positions...")