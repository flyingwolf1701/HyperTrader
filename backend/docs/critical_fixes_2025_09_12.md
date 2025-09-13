# Critical Fixes - September 12, 2025

## Issues Identified

1. **Price callback not being triggered on every price update**
   - WebSocket was only calling price_callback when unit_changed was True
   - This prevented main.py from tracking all prices and detecting unit changes properly
   
2. **Order ID format mismatch**
   - Order IDs from fills might not match stored IDs in position_map
   - Added explicit string conversion and detailed logging

3. **Old fills appearing in logs**
   - Bot was processing fills from before startup time
   - Added timestamp filtering to skip old fills

## Fixes Applied

### 1. WebSocket Price Callback Fix (CRITICAL)
**File:** `backend/src/core/websocket_client.py`

**Before:**
```python
# Only called callback on unit changes
if unit_changed:
    if coin in self.price_callbacks and self.price_callbacks[coin] is not None:
        self.price_callbacks[coin](Decimal(str(price)))
```

**After:**
```python
# ALWAYS call price callback for EVERY price update
if coin in self.price_callbacks and self.price_callbacks[coin] is not None:
    self.price_callbacks[coin](Decimal(str(price)))

# Check for unit changes (for logging purposes)
unit_changed = tracker.calculate_unit_change(price)
```

**Impact:** This ensures `_handle_price_update()` in main.py receives ALL price updates, allowing it to:
- Track current price continuously
- Detect unit boundaries properly
- Trigger sliding window actions when needed

### 2. Order ID Tracking and Logging
**Files:** `backend/src/main.py`, `backend/src/core/websocket_client.py`

Added comprehensive logging to track order IDs:
- Log order ID when placing orders: `ORDER ID TRACKING: Stop-loss at unit X = {order_id}`
- Log order ID when receiving fills: `FILL CALLBACK: Passing order_id={oid}`
- Log position_map contents when trying to match: `Active orders in position_map: {active_orders}`

### 3. Order ID Type Consistency
**File:** `backend/src/core/websocket_client.py`

Ensured order IDs are always strings:
```python
await self.fill_callbacks[coin](
    str(oid),      # order_id - ensure it's a string
    price,         # filled_price  
    size           # filled_size
)
```

### 4. Fill Timestamp Filtering
**File:** `backend/src/core/websocket_client.py`

Already implemented - filters out fills from before bot startup:
```python
if time_ms:
    fill_time = datetime.fromtimestamp(time_ms / 1000)
    if fill_time < self.startup_time:
        logger.debug(f"Skipping old fill from {fill_time}")
        continue
```

## Expected Behavior After Fixes

1. **Price Updates:** Bot will receive and process EVERY price update from WebSocket
2. **Unit Changes:** Unit boundary crossings will be detected correctly
3. **Sliding Window:** Window sliding actions will execute when units change
4. **Order Tracking:** Clear logging shows order ID flow from placement to fill
5. **Fill Matching:** Order fills should match correctly with position_map entries

## Testing Recommendations

1. Run the bot and watch for:
   - "Price update received: $X" messages (should appear frequently)
   - "UNIT EVENT DETECTED" when price crosses unit boundaries
   - "ORDER ID TRACKING" messages when orders are placed
   - "FILL RECEIVED" with matching order IDs

2. Verify sliding window behavior:
   - When price rises, new stops should be added at current-1
   - When price falls and stops trigger, replacement buys should be placed at current+1
   - Window should maintain 4 total orders

3. Check order ID matching:
   - Order IDs in "ORDER ID TRACKING" logs should match IDs in "FILL RECEIVED" logs
   - No more "Could not match order X to any unit" errors

## Critical Fix Priority

**HIGHEST PRIORITY:** The WebSocket price callback fix is the most critical - without it, the bot cannot detect unit changes or trigger sliding window actions properly.