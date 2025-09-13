# Complete Sliding Window Fix - Handling Rapid Price Movements

## Problem Identified
When price drops rapidly (e.g., from unit 0 to unit -6), all stop-loss orders trigger but the bot was only placing ONE replacement buy order instead of maintaining 4 trailing buy orders.

## Root Cause
The original `_slide_window_down()` logic only handled single unit movements. It would:
1. Check if current_unit had a stop
2. Place ONE buy at current_unit + 1
3. Ignore all other triggered stops

This meant during rapid price drops, only one buy order would be placed, leaving the position vulnerable.

## The Fix

### Downward Movement (Price Drops)
```python
async def _slide_window_down(self):
    # When price drops to current_unit:
    # 1. Remove ALL stops at or above current_unit (they triggered)
    # 2. Place 4 trailing buy orders at current_unit +1, +2, +3, +4
    # 3. Cancel any buy orders above current_unit + 4
```

**Example:** Price drops from 0 to -6
- **Before:** Stops at [-4, -3, -2, -1]
- **Triggers:** All 4 stops trigger (they're all >= -6)
- **After:** Buys at [-5, -4, -3, -2] (4 orders trailing the price)

### Upward Movement (Price Rises)
```python
async def _slide_window_up(self):
    # When price rises to current_unit:
    # 1. Remove ALL buys at or below current_unit (they executed)
    # 2. Place 4 trailing stop orders at current_unit -1, -2, -3, -4
    # 3. Cancel any stop orders below current_unit - 4
```

**Example:** Price rises from -6 to 0
- **Before:** Buys at [-5, -4, -3, -2]
- **Executes:** All 4 buys execute (they're all <= 0)
- **After:** Stops at [-1, -2, -3, -4] (4 orders trailing the price)

## Key Improvements

1. **Handles Rapid Movements:** Works correctly whether price moves 1 unit or 10 units
2. **Always Maintains 4 Orders:** Ensures exactly 4 orders are always active
3. **Proper Trailing:** Orders follow the price in the appropriate direction
4. **Clean Old Orders:** Cancels orders that are now too far from current price

## Expected Behavior

### Scenario: Rapid Drop from Unit 0 to -6

**Initial State:**
- Position at unit 0
- Stops at [-4, -3, -2, -1]
- No buy orders

**After Drop to -6:**
- All stops triggered (removed from tracking)
- 4 new buy orders placed at [-5, -4, -3, -2]
- Ready to catch rebounds

**If Price Continues to -7:**
- Buy orders slide down to [-6, -5, -4, -3]
- Old buy at -2 cancelled

**If Price Recovers to -5:**
- Buy at -5 executes
- New stop placed at -6
- Remaining buys at [-4, -3, -2]

## Testing Checklist

✅ **Rapid Drop Test:**
- Drop from 0 to -6 should place 4 buy orders
- Further drops should trail the buy orders down

✅ **Rapid Rise Test:**
- Rise from -6 to 0 should place 4 stop orders
- Further rises should trail the stop orders up

✅ **Oscillation Test:**
- Quick moves between units should maintain 4 orders
- No orphaned orders left behind

## Log Messages to Verify

When working correctly, you'll see:

**On Drop:**
```
Sliding window DOWN to unit -6
Stops triggered at units: [-4, -3, -2, -1]
Desired trailing buy units: [-5, -4, -3, -2]
✅ Added trailing buy at unit -5
✅ Added trailing buy at unit -4
✅ Added trailing buy at unit -3
✅ Added trailing buy at unit -2
After slide: Stops=[], Buys=[-5, -4, -3, -2]
```

**On Rise:**
```
Sliding window UP to unit 0
Buy orders executed at units: [-5, -4, -3, -2]
Desired trailing stop units: [-1, -2, -3, -4]
✅ Added trailing stop at unit -1
✅ Added trailing stop at unit -2
✅ Added trailing stop at unit -3
✅ Added trailing stop at unit -4
After slide: Stops=[-4, -3, -2, -1], Buys=[]
```

## Summary
The sliding window now properly handles rapid price movements in both directions, always maintaining exactly 4 orders that trail the current price. This provides consistent protection and opportunity capture regardless of how fast the market moves.