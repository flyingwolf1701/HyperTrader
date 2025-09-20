# Position Map Issues and Proposed Solutions (Long Wallet Focus)

## Document Version Analysis
- **Strategy Doc Version**: v9.4.12
- **Position Map Version**: v9.2.6 (outdated)

## Critical Issues for Long Wallet

### 1. Missing Stop-Loss Order Type
**Problem**: Position map only has `LIMIT_SELL` and `LIMIT_BUY`. The long wallet strategy explicitly requires stop-loss orders that trail price, not limit sell orders.

**Proposed Solution**:
```python
class OrderType(Enum):
    STOP_LOSS_SELL = "stop_loss_sell"    # Stop-loss for long positions
    LIMIT_BUY = "limit_buy"               # Long wallet buy
    MARKET_SELL = "market_sell"           # For emergency exits
    MARKET_BUY = "market_buy"             # For position entry
```

### 2. Incorrect Order Windows Tracking
**Problem**: Current implementation tracks single generic window. Long wallet strategy requires two distinct windows:
- `stop_loss_orders`: 4 trailing stop-losses 
- `limit_buy_orders`: 4 limit buys ahead of price

**Proposed Solution**: Track multiple window types:
```python
@dataclass
class PositionConfig:
    # Remove: in_window, window_position
    # Add:
    window_type: Optional[str] = None  # "stop_loss_orders" or "limit_buy_orders"
    window_index: Optional[int] = None # Position within specific window (0-3)
```

### 3. Missing Stop-Loss Order Logic
**Problem**: Strategy uses stop-loss orders that execute when price falls TO or BELOW trigger, but position map only handles limit orders.

**Proposed Solution**: Add stop-loss specific handling:
- Stop-loss orders execute when price reaches or falls below trigger
- Different execution logic than limit orders
- Must track whether order is stop or limit type

### 4. Missing Phase Tracking
**Problem**: No phase tracking (ADVANCE, RETRACEMENT, DECLINE, RECOVERY, RESET) which is critical for long wallet strategy execution.

**Proposed Solution**: Phase tracking should be in unit_tracker.py, but position_map needs to support it:
```python
# This belongs in unit_tracker.py but position_map should be aware
class Phase(Enum):
    ADVANCE = "advance"
    RETRACEMENT = "retracement"
    DECLINE = "decline"
    RECOVERY = "RECOVERY"
    RESET = "reset"
```

### 5. Incorrect Order Replacement Logic
**Problem**: Current `handle_order_replacement` doesn't distinguish between stop-loss and limit order replacements:
- Stop-loss triggers → Place limit buy at current+1
- Limit buy fills → Place stop-loss at current-1 (not generic "sell")

**Proposed Solution**: Update replacement logic to handle order types correctly:
```python
def handle_order_replacement(position_map, executed_unit, current_unit, order_type):
    if order_type == OrderType.STOP_LOSS_SELL:
        # Replace with limit buy at current+1
        replacement_type = OrderType.LIMIT_BUY
        replacement_unit = current_unit + 1
    elif order_type == OrderType.LIMIT_BUY:
        # Replace with stop-loss at current-1
        replacement_type = OrderType.STOP_LOSS_SELL
        replacement_unit = current_unit - 1
```

### 6. Missing RESET Mechanism Support
**Problem**: No support for RESET logic that:
- Helps track when to reset unit counters to 0
- Updates allocation with compounded values
- Tracks cycle completion

**Proposed Solution**: Add cycle tracking to PositionState:
```python
@dataclass
class PositionState:
    # Add cycle tracking
    cycle_number: int = 0
    cycle_start_value: Decimal = Decimal("0")
    cumulative_growth: Decimal = Decimal("1.0")
```

## Summary of Required Changes for Long Wallet

1. **Add stop-loss order type** (STOP_LOSS_SELL) distinct from LIMIT_SELL
2. **Support two order windows**: stop_loss_orders and limit_buy_orders
3. **Implement stop-order logic** with proper trigger conditions
4. **Fix order replacement logic** to handle stop-loss vs limit correctly
5. **Add RESET mechanism support** for cycle tracking and compounding
6. **Add validation** for order type combinations

## Priority Recommendations

**High Priority**:
- Add STOP_LOSS_SELL order type
- Support multiple window tracking (stop_loss_orders, limit_buy_orders)

**Medium Priority**:
- Implement proper order replacement logic
- Add RESET mechanism support

**Low Priority**:
- Add extensive logging for debugging
- Implement order validation rules