#!/usr/bin/env python3
"""Test RETRACEMENT logic by simulating price movements"""

import json
import os

# Load current state
with open("strategy_state.json", "r") as f:
    state = json.load(f)

print(f"Current state: Unit {state['current_unit']}, Peak {state['peak_unit']}, Phase {state['phase']}")
print(f"Current position: ${state['current_long_position']}")

# Simulate a drop of 5 units from peak
# This should trigger sells and shorts
new_price = state['entry_price'] - (2.5)  # Drop by 2.5 dollars (5 units at 0.5 per unit)
state['last_price'] = new_price

# Save modified state
with open("strategy_state.json", "w") as f:
    json.dump(state, f, indent=2)

print(f"\nSimulated price drop to ${new_price}")
print("Now run update to trigger RETRACEMENT trades...")