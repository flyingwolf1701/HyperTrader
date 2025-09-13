# Main.py Issues and Proposed Solutions (Long Wallet Focus)

## Document Version Analysis
- **Strategy Doc Version**: v9.4.12
- **Main.py Version**: v9.2.6 (outdated)

## Critical Issues for Long Wallet

### 1. Incorrect Order Types
**Problem**: Uses generic "stop losses" but long wallet needs distinct order types:
- Stop-loss orders (STOP_LOSS_SELL) that trigger when price falls
- Limit buy orders (LIMIT_BUY) that execute at specific prices
- Different execution and replacement logic for each

**Proposed Solution**:
```python
async def _place_stop_loss_order(self, unit: int) -> Optional[str]:
    # Place STOP_LOSS_SELL order that triggers when price <= trigger_price
    # Size: self.position_state.long_fragment_asset (25% of position)
    
async def _place_limit_buy_order(self, unit: int) -> Optional[str]:
    # Place LIMIT_BUY order at specific price
    # Size: self.position_state.long_fragment_usd / price
```

### 2. Wrong Initial Order Placement
**Problem**: Places generic orders but strategy specifies:
- Long wallet: 4 stop-loss orders at [current-4, current-3, current-2, current-1]
- These are STOP_LOSS_SELL orders, not generic sells

**Proposed Solution**:
```python
async def _place_window_orders(self):
    # Long wallet: Place 4 stop-losses
    for unit in [-4, -3, -2, -1]:
        await self._place_stop_loss_order(self.current_unit + unit)
```

### 3. Missing Dual Window Management
**Problem**: Doesn't track two separate windows for long wallet:
- `stop_loss_orders` window (4 stop-losses)
- `limit_buy_orders` window (4 limit buys when in DECLINE/RECOVER)

**Proposed Solution**: Track both windows separately in unit_tracker and coordinate in main:
```python
async def _place_order_based_on_window(self, unit: int, window_type: str):
    if window_type == "stop_loss_orders":
        await self._place_stop_loss_order(unit)
    elif window_type == "limit_buy_orders":
        await self._place_limit_buy_order(unit)
```

### 4. Incorrect Window Sliding Logic
**Problem**: Current sliding logic doesn't match strategy:
- ADVANCE: Stop-losses should trail at [current-4, current-3, current-2, current-1]
- DECLINE: Limit buys should trail at [current+1, current+2, current+3, current+4]

**Proposed Solution**:
```python
async def _slide_window(self, direction: str):
    if direction == 'up' and self.phase == Phase.ADVANCE:
        # Add stop-loss at (current-1), cancel at (current-5)
        new_unit = self.current_unit - 1
        old_unit = self.current_unit - 5
        
    elif direction == 'down' and self.phase == Phase.DECLINE:
        # Add limit buy at (current+1), cancel at (current+5)
        new_unit = self.current_unit + 1
        old_unit = self.current_unit + 5
```

### 5. Incorrect Order Replacement Logic
**Problem**: Doesn't properly handle order type replacements:
- Stop-loss triggers → Should place LIMIT_BUY at current+1
- Limit buy fills → Should place STOP_LOSS_SELL at current-1

**Proposed Solution**:
```python
async def handle_order_fill(self, order_id: str, order_type: OrderType):
    if order_type == OrderType.STOP_LOSS_SELL:
        # Place limit buy at current+1
        replacement_unit = self.current_unit + 1
        await self._place_limit_buy_order(replacement_unit)
    elif order_type == OrderType.LIMIT_BUY:
        # Place stop-loss at current-1
        replacement_unit = self.current_unit - 1
        await self._place_stop_loss_order(replacement_unit)
```

### 6. Incomplete RESET Implementation
**Problem**: RESET doesn't properly capture compound growth for long wallet:
- Should reset unit counters to 0
- Should update fragment sizes based on new position value
- Should reinitialize windows correctly

**Proposed Solution**:
```python
async def _handle_reset(self):
    # Get current position value (with growth)
    new_position_value = position.size * self.current_price
    
    # Calculate growth factor
    growth_factor = new_position_value / self.position_state.original_position_value_usd
    logger.info(f"RESET: Compound growth {growth_factor:.2%}")
    
    # Update position state with new values
    self.position_state.original_asset_size = position.size
    self.position_state.original_position_value_usd = new_position_value
    
    # Recalculate fragments based on new size
    self.position_state.long_fragment_asset = position.size / 4
    self.position_state.long_fragment_usd = new_position_value / 4
    
    # Reset unit tracker
    self.unit_tracker.reset_for_new_cycle(self.current_price)
    
    # Cancel all orders and reinitialize windows
    await self._cancel_all_orders()
    await self._place_window_orders()
```

### 7. Missing Phase-Specific Order Management
**Problem**: Doesn't adjust order placement based on phase transitions.

**Proposed Solution**: Add phase-aware order management:
```python
async def _handle_phase_transition(self, old_phase: Phase, new_phase: Phase):
    if old_phase == Phase.ADVANCE and new_phase == Phase.RETRACEMENT:
        # First stop-loss triggered, entering mixed state
        logger.info("Entering RETRACEMENT - mixed orders")
    elif old_phase == Phase.RETRACEMENT and new_phase == Phase.DECLINE:
        # All stop-losses triggered, switch to all limit buys
        logger.info("Entering DECLINE - all limit buys")
```

### 8. No Compound Growth Tracking
**Problem**: RESET updates position but doesn't properly track growth metrics over time.

**Proposed Solution**: Add cumulative tracking:
```python
class GrowthTracker:
    cycle_count: int = 0
    cumulative_growth: Decimal = Decimal("1.0")
    cycle_start_value: Decimal
    cycle_end_value: Decimal
```

### 9. Incomplete Error Recovery
**Problem**: No recovery mechanism if orders fail or connection drops.

**Proposed Solution**: Add retry logic:
```python
async def _place_order_with_retry(self, order_func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await order_func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

### 10. Missing Position Validation
**Problem**: Doesn't validate actual position matches expected state.

**Proposed Solution**: Add position reconciliation:
```python
async def _validate_position_state(self):
    actual_position = self.sdk_client.get_positions()[self.symbol]
    expected_size = self.position_state.asset_size
    
    if abs(actual_position.size - expected_size) > 0.0001:
        logger.warning(f"Position mismatch: actual={actual_position.size}, expected={expected_size}")
```

## Summary of Required Changes for Long Wallet

1. **Use correct order types** (STOP_LOSS_SELL vs LIMIT_BUY)
2. **Fix initial order placement** (4 stop-losses at correct units)
3. **Implement dual window management** (stop_loss_orders and limit_buy_orders)
4. **Fix window sliding logic** for both ADVANCE and DECLINE phases
5. **Correct order replacement logic** based on order type
6. **Complete RESET implementation** with proper compounding
7. **Add phase-specific order management**
8. **Track compound growth** properly
9. **Implement error recovery** with retries
10. **Add position validation** and reconciliation

## Priority Recommendations

**High Priority**:
- Use correct order types (stop-loss vs limit)
- Fix initial order placement
- Implement dual window tracking

**Medium Priority**:
- Fix window sliding logic
- Complete RESET implementation
- Add position validation

**Low Priority**:
- Add error recovery
- Track compound growth metrics
- Enhance logging