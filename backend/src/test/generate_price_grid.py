from decimal import Decimal
import os
import sys

# --- FIX: Add project root to Python's path ---
# This allows the script to be run from anywhere and still find the 'src' package.
# It calculates the path to the 'backend' directory and adds it.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# --- End of FIX ---

from src.strategy.unit_tracker import UnitTracker

# --- Configuration ---
# You can change these values to match your main.py config
STARTING_PRICE = Decimal("150.0")
GRID_SPACING = Decimal("0.01")  # 1%
TARGET_UNITS = 100

def generate_and_print_grid():
    """
    Initializes a UnitTracker and prints the full price grid around the starting price.
    """
    print("--- HyperTrader Price Grid Visualization ---")
    print(f"Starting Price: ${STARTING_PRICE}")
    print(f"Grid Spacing: {GRID_SPACING * 100}%")
    print(f"Target Units: {TARGET_UNITS}")
    print("-" * 40)

    # Initialize the UnitTracker
    unit_tracker = UnitTracker(grid_spacing=GRID_SPACING, target_units=TARGET_UNITS)
    unit_tracker.current_price = STARTING_PRICE
    
    # Calculate the current unit index based on the starting price
    # This centers the grid around the current market price
    current_unit_index = unit_tracker.price_to_unit(STARTING_PRICE)
    unit_tracker.units_held = current_unit_index

    print(f"{'Unit Index':<15} | {'Calculated Price':<20}")
    print(f"{'-'*15} | {'-'*20}")

    # Generate prices for the grid, centered around the current unit
    # We'll show +/- 10 units around the center for readability, plus the extremes
    display_range = 10
    
    # Header for sell grid (short positions)
    print("--- SELL GRID (Short Zone) ---")
    for i in range(display_range, 0, -1):
        unit_index = current_unit_index + i
        price = unit_tracker.unit_to_price(unit_index)
        print(f"{unit_index:<15} | ${price:<20,.4f}")

    # Center of the grid
    print(f"{'-'*15} | {'-'*20}")
    center_price = unit_tracker.unit_to_price(current_unit_index)
    print(f"{current_unit_index:<15} | ${center_price:<20,.4f} <-- STARTING POINT")
    print(f"{'-'*15} | {'-'*20}")

    # Header for buy grid (long positions)
    print("--- BUY GRID (Long Zone) ---")
    for i in range(1, display_range + 1):
        unit_index = current_unit_index - i
        price = unit_tracker.unit_to_price(unit_index)
        print(f"{unit_index:<15} | ${price:<20,.4f}")

    # Show extreme values
    print(f"{'-'*15} | {'-'*20}")
    print("--- EXTREME GRID POINTS ---")
    max_short_price = unit_tracker.unit_to_price(TARGET_UNITS)
    max_long_price = unit_tracker.unit_to_price(-TARGET_UNITS)
    print(f"{TARGET_UNITS:<15} | ${max_short_price:<20,.4f} (Max Short)")
    print(f"{-TARGET_UNITS:<15} | ${max_long_price:<20,.4f} (Max Long)")
    print("-" * 40)


if __name__ == "__main__":
    generate_and_print_grid()
```

#### How to Run the Script Now
With this fix, you can run the script from the `backend` directory as you were trying to:
```bash
# Make sure you are in the 'backend' directory
python scripts/generate_price_grid.py
```

### 2. Fixing the `pytest` Error

The `pytest` error is happening for the exact same reason: `pytest` can't find the `src` directory when it tries to import your test file. This is made worse because the standard convention is to have the `tests` directory at the same level as `src`, not inside it.

Here is the most robust and conventional way to fix this for good:

**Step 1: Restructure Your Test Directory**
* Move your test directory from `backend/src/test` to `backend/tests`.

**Step 2: Run `pytest` from the Root**
* Navigate to your `backend` directory in the terminal.
* Run the `pytest` command by itself. It will automatically discover and run all your test files.

```bash
# Make sure you are in the 'backend' directory
pytest
```

If you want to run only one file, you can now do so easily:
```bash
# From the 'backend' directory
pytest tests/test_overall.py

