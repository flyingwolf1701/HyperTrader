# Hyperliquid Limit Buy Order Analysis

## The Core Problem

When attempting to place limit buy orders above the current market price on Hyperliquid, we encounter a fundamental issue:
- **Regular limit buy orders above market price will execute immediately** (acting like market orders)
- We need orders that **wait for price to RISE** to a specific level before buying
- This is essential for the sliding window strategy where we want to buy back at higher prices after stop-losses trigger

## Hyperliquid Order Types Available

### 1. Regular Limit Orders
- **Behavior**: Execute at specified price or better
- **Issue**: Buy limits above market execute immediately
- **Use Case**: Only works for buy orders below market price

### 2. Stop Orders (Stop Loss)
- **Type**: `tpsl: "sl"` 
- **Trigger**: When price moves against your position
- **Variants**: Can be market or limit when triggered
- **Current Use**: We use these for stop-loss sells below market

### 3. Take Profit Orders
- **Type**: `tpsl: "tp"`
- **Trigger**: When price moves in favor of your position
- **Variants**: Can be market or limit when triggered
- **Potential Use**: Could trigger buys when price rises

### 4. Stop Limit Orders
- **Behavior**: Becomes an active limit order when trigger price is reached
- **Configuration**: `trigger: { triggerPx, isMarket: false, tpsl: "sl" or "tp" }`
- **Use Case**: Can wait for price to reach a level before activating

## Solution Options

### Option 1: Stop Limit Buy Orders (Most Aligned with Intent)
**How it works:**
- Place stop limit buy orders with trigger price at desired level above market
- When price rises to trigger, order becomes active limit order
- Would use `tpsl: "tp"` for buys above market (take profit on short)

**Pros:**
- Orders wait dormant until price reaches target
- Exact execution at desired price levels
- Maintains the "sliding window" concept

**Cons:**
- May need SDK modifications to support "tp" type for entries
- More complex order management

**Implementation:**
```python
def place_stop_limit_buy(trigger_price, limit_price, size):
    order_type = {
        "trigger": {
            "triggerPx": float(trigger_price),
            "isMarket": False,  # Execute as limit
            "tpsl": "tp"  # Take profit type for upward trigger
        }
    }
```

### Option 2: Take Profit Orders for Entry
**How it works:**
- Use take profit orders to trigger buys when price rises
- Repurpose TP orders as entry mechanisms

**Pros:**
- Native support in Hyperliquid
- Clear trigger mechanism

**Cons:**
- Semantically confusing (TP usually for exits)
- May have position requirements

### Option 3: Real-time Price Monitoring with Market Orders
**How it works:**
- Don't pre-place orders above market
- Monitor price continuously
- When price reaches target unit, immediately place market buy

**Pros:**
- Guaranteed execution when price reached
- No order type complications
- Simple implementation

**Cons:**
- Requires constant monitoring
- Potential slippage with market orders
- Less "set and forget"

**Implementation:**
```python
async def monitor_and_buy(target_price, size):
    while True:
        current_price = await get_current_price()
        if current_price >= target_price:
            await place_market_order("buy", size)
            break
        await asyncio.sleep(1)
```

### Option 4: Conditional Orders (If Supported)
**How it works:**
- Use conditional/OCO (One-Cancels-Other) orders if available
- Set conditions for order activation

**Status:** Need to verify if Hyperliquid supports these

### Option 5: Regular Limit Orders with Continuous Adjustment
**How it works:**
- Place limit buy just below market
- Continuously adjust upward as price rises
- Convert to market order when target reached

**Pros:**
- Works with standard order types
- Maintains order book presence

**Cons:**
- High API usage
- Complex tracking logic
- Risk of execution at wrong price

## Recommended Approach

### Primary: Option 1 - Stop Limit Buy Orders
This most closely matches the strategy's intent:
1. Modify SDK to add `place_stop_limit_buy()` function
2. Use `tpsl: "tp"` for upward triggers on buy orders
3. Set trigger at target unit price
4. Execute as limit order when triggered

### Fallback: Option 3 - Price Monitoring
If stop limit buys don't work as expected:
1. Track target buy levels in memory
2. Monitor price via WebSocket
3. Execute market buys when price reaches targets
4. More reactive but guarantees execution

## Implementation Considerations

### Current Code Issues
1. `post_only=True` prevents immediate execution but causes rejection
2. Price adjustment code (buy $1 below market) defeats the purpose
3. Need to distinguish between orders meant to execute now vs. later

### Required Changes
1. **SDK Enhancement**: Add support for stop limit buy orders
2. **Order Type Selection**: Logic to choose regular limit (below market) vs stop limit (above market)
3. **Logging**: Clear indication of order type being placed
4. **Error Handling**: Graceful fallback if stop limits fail

## Testing Strategy
1. Place stop limit buy above market, verify it doesn't execute immediately
2. Wait for price to rise to trigger level
3. Confirm order activates and fills correctly
4. Test with various market conditions (volatile, stable, gaps)

## Next Steps
1. Implement `place_stop_limit_buy()` in SDK
2. Update `_place_limit_buy_order()` to detect above/below market
3. Use appropriate order type based on price comparison
4. Add comprehensive logging for debugging
5. Test in testnet environment first