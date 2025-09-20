# Trailing Order Issues Analysis

## Overview
This document analyzes why the trailing order system isn't working correctly despite the code appearing logically sound. The bot places initial orders correctly but fails to maintain the trailing window during price movement.

## Where Order Management Is Handled

### 1. Price Update Reception
**Location:** `main.py` lines 417-430 (`_handle_price_update`)
```python
def _handle_price_update(self, price: Decimal):
    self.current_price = price
    unit_event = self.unit_tracker.calculate_unit_change(price)
    if unit_event:
        asyncio.create_task(self._handle_unit_change(unit_event))
```

**Why Code Thinks It Works:**
- Every price update from WebSocket triggers this
- Should detect every unit boundary crossing
- Spawns async task to handle changes immediately

### 2. Unit Boundary Detection
**Location:** `unit_tracker.py` lines 46-96 (`calculate_unit_change`)
```python
def calculate_unit_change(self, price: Decimal) -> Optional[UnitChangeEvent]:
    new_unit = self._calculate_unit_for_price(price)
    if new_unit != self.current_unit:
        # Detects crossing and returns event
```

**Why Code Thinks It Works:**
- Mathematically calculates which unit the price is in
- Compares to previous unit
- Returns event with direction ('up' or 'down')

### 3. Unit Change Response
**Location:** `main.py` lines 431-513 (`_handle_unit_change`)

**For UP Movement:**
```python
if event.direction == 'up':
    new_stop_unit = current_unit - 1
    # Place new stop at current_unit - 1
    # Cancel oldest stop if > 4
```

**For DOWN Movement:**
```python
elif event.direction == 'down':
    new_buy_unit = current_unit + 1
    # Place new buy at current_unit + 1
    # Cancel oldest buy if > 4
```

**Why Code Thinks It Works:**
- Places one new order per unit crossing
- Maintains 4-order window by removing oldest
- Updates tracking lists

### 4. Order Tracking Lists
**Location:** `unit_tracker.py` lines 36-37
```python
self.trailing_stop: List[int] = [-4, -3, -2, -1]  # Initial stops
self.trailing_buy: List[int] = []  # Initially empty
```

**Why Code Thinks It Works:**
- Simple list-based tracking
- Add/remove methods maintain the lists
- Always sorted for readability

## Why The Code ISN'T Actually Working

### Problem 1: Rapid Price Movement
**The Fatal Assumption:** Code assumes price moves one unit at a time.

**What Actually Happens:**
- Price jumps from unit 5 → unit 12 in one tick
- `calculate_unit_change` sees: old_unit=5, new_unit=12, direction='up'
- `_handle_unit_change` places ONE stop at unit 11
- **MISSING:** Stops at units 8, 9, 10

**Where It Breaks:** Lines 458-467 in `main.py`
- Only places stop at `current_unit - 1`
- Should place stops at ALL units from `(current_unit - 4)` to `(current_unit - 1)`

### Problem 2: No Order ID → Unit Mapping
**The Inefficiency:** Must search entire position_map to find order's unit.

**What Actually Happens:**
- Order fill comes in with order_id "xyz123"
- Code loops through ENTIRE position_map (lines 553-559)
- O(n) search for every fill
- If position_map is large or corrupted, may not find match

**Where It Breaks:** Lines 535-619 in `main.py` (`handle_order_fill`)
```python
for unit, config in self.position_map.items():
    if config.order_id == order_id:
        filled_unit = unit
        # ... rest of logic
```

### Problem 3: No State Validation
**The Blind Spot:** Code never verifies orders actually exist on exchange.

**What Actually Happens:**
- Order placement fails (network issue, invalid price, etc.)
- List still shows order at that unit
- System thinks it has 4 stops, really has 3
- Never attempts to repair the window

**Where It Should Exist But Doesn't:**
- No periodic validation in main loop
- No reconciliation with exchange state
- No recovery mechanism

### Problem 4: Phase Transitions Not Handled
**The Edge Case:** When switching between ADVANCE and DECLINE phases.

**What Should Happen:**
- Clear all stops, place all buys (or vice versa)
- Ensure full 4-order window immediately

**What Actually Happens:**
- Gradual transition
- May have mixed state for extended periods
- Window not properly maintained during transition

## Critical Code Locations

### Where Orders Are Placed:
1. **Initial Setup:** `_place_window_orders()` lines 208-228
2. **Stop Loss:** `_place_stop_loss_order()` lines 341-387
3. **Stop Buy:** `_place_stop_buy_order()` lines 257-339
4. **Unit Change:** `_handle_unit_change()` lines 431-513

### Where Orders Are Tracked:
1. **Lists:** `unit_tracker.py` lines 36-37
2. **Add/Remove:** `unit_tracker.py` lines 190-222
3. **Position Map:** Updated in place methods above

### Where Orders Should Be Validated (But Aren't):
1. After each unit change
2. In main loop periodically
3. After order placement attempts
4. After fill processing

## The Core Issue

The system is **event-driven** but assumes **sequential events**. It handles:
- Unit 5 → 6 → 7 → 8 (works fine)

But fails on:
- Unit 5 → 12 (misses intermediate units)
- Network delays causing out-of-order events
- Failed order placements not being retried

## What's Needed (Conceptually)

1. **Order ID Dictionary:**
   - `order_id_to_unit: Dict[str, int]`
   - Fast O(1) lookups
   - Single source of truth

2. **Window Repair Logic:**
   - After unit change, ensure ALL 4 orders exist
   - Place multiple orders if needed
   - Don't assume single-unit movements

3. **State Validation:**
   - Periodic check: "Do I have 4 trailing orders?"
   - If not, place missing ones
   - Cancel any outside window

4. **Robust Fill Handling:**
   - Direct order_id lookup
   - Handle duplicates
   - Log unmatched orders

## Summary

The code is architecturally sound for **gradual price movement** but breaks down under:
- Rapid multi-unit price jumps
- Network issues causing failed placements
- Out-of-order or duplicate events
- Lack of state validation/recovery

The trailing orders aren't being placed because the code only handles single-unit movements and has no mechanism to "fill in" gaps when price jumps multiple units at once.