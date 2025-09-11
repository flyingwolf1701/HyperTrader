# Unit Tracker Issues and Proposed Solutions (Long Wallet Focus)

## Document Version Analysis
- **Strategy Doc Version**: v9.4.12
- **Unit Tracker Version**: v9.2.6 (outdated)

## Critical Issues for Long Wallet

### 1. Missing Stop-Loss Order Support
**Problem**: Unit tracker only handles generic "sell" and "buy" orders, but long wallet strategy explicitly requires:
- Stop-loss orders (trigger when price falls TO or BELOW)
- Different execution logic for stops vs limits

**Proposed Solution**:
```python
def handle_order_execution(self, executed_unit: int, order_type: OrderType):
    # OrderType.STOP_LOSS_SELL or OrderType.LIMIT_BUY
    # Each has different replacement logic
```

### 2. Single Window Instead of Two Windows
**Problem**: Current implementation uses single `SlidingWindow` but long wallet requires two separate windows:
- `stop_loss_orders`: 4 trailing stop-losses behind price
- `limit_buy_orders`: 4 limit buys ahead of price (when in DECLINE/RECOVER)

**Proposed Solution**: Replace single window with dual window management:
```python
@dataclass
class LongWalletWindows:
    stop_loss_orders: List[int] = field(default_factory=list)  # 4 trailing stop-losses
    limit_buy_orders: List[int] = field(default_factory=list)   # 4 limit buys ahead of price
    
    def total_orders(self) -> int:
        return len(self.stop_loss_orders) + len(self.limit_buy_orders)
    
    def is_all_stop_losses(self) -> bool:
        return len(self.stop_loss_orders) == 4 and len(self.limit_buy_orders) == 0
    
    def is_all_limit_buys(self) -> bool:
        return len(self.limit_buy_orders) == 4 and len(self.stop_loss_orders) == 0
```

### 3. Incorrect Order Replacement Logic
**Problem**: Current replacement uses generic "sell"/"buy" but long wallet needs:
- Stop-loss triggers → Place limit buy at current+1 ✓
- Limit buy fills → Place stop-loss at current-1 (not generic "sell")

**Proposed Solution**: Implement order-type-aware replacement:
```python
def handle_order_execution(self, executed_unit: int, order_type: OrderType):
    if order_type == OrderType.STOP_LOSS_SELL:
        # Remove from stop_loss_orders window
        # Add limit buy at current+1 to limit_buy_orders window
    elif order_type == OrderType.LIMIT_BUY:
        # Remove from limit_buy_orders window
        # Add stop-loss at current-1 to stop_loss_orders window
```

### 4. Incorrect Window Sliding Logic
**Problem**: Current sliding only handles simple sell/buy windows, but long wallet needs:
- In ADVANCE: Stop-losses trail at [current-4, current-3, current-2, current-1]
- In DECLINE: Limit buys trail at [current+1, current+2, current+3, current+4]

**Proposed Solution**: Implement proper sliding for both windows:
```python
def _slide_window(self, direction: str):
    if direction == 'up' and self.phase == Phase.ADVANCE:
        # Add stop-loss at current-1, remove at current-5
        new_stop = self.current_unit - 1
        old_stop = self.current_unit - 5
        
    elif direction == 'down' and self.phase == Phase.DECLINE:
        # Add limit buy at current+1, remove at current+5
        new_buy = self.current_unit + 1
        old_buy = self.current_unit + 5
```

### 5. Incorrect Initial Order Configuration
**Problem**: Strategy specifies initial orders should be stop-losses, not generic "sells":
- Long wallet: 4 stop-loss orders at [current-4, current-3, current-2, current-1]

**Proposed Solution**: Update initialization to use proper order types:
```python
def _initialize_long_window(self):
    self.windows.stop_loss_orders = [-4, -3, -2, -1]
    self.windows.limit_buy_orders = []  # Empty initially
    self.phase = Phase.ADVANCE
```

### 6. Missing Position State Integration for RESET
**Problem**: RESET detection needs to know when returning to 100% long from mixed phases.

**Proposed Solution**: Track position composition:
```python
def _should_reset(self) -> bool:
    # Long wallet: All limit buys executed in RECOVER phase
    if self.phase == Phase.RECOVER and self.windows.is_all_stop_losses():
        return True
    # Also check RETRACEMENT returning to full long
    if self.phase == Phase.RETRACEMENT and self.windows.is_all_stop_losses():
        return True
    return False
```

### 7. No Compound Growth Tracking
**Problem**: RESET should capture compound growth but doesn't track position value changes.

**Proposed Solution**: Track position value evolution:
```python
@dataclass
class CompoundTracking:
    initial_value: Decimal
    current_value: Decimal
    growth_factor: Decimal
```

### 8. Incomplete Logging
**Problem**: Missing critical logging for:
- Order type distinctions (stop-loss vs limit)
- Phase transitions with position details

**Proposed Solution**: Add comprehensive logging with order type details.

## Summary of Required Changes for Long Wallet

1. **Add stop-loss order handling** (distinct from generic "sell")
2. **Replace single window with dual window management** (stop_loss_orders and limit_buy_orders)
3. **Fix order replacement logic** for stop-loss vs limit buy
4. **Implement proper window sliding** for both windows
5. **Use correct initial order types** (stop-losses, not generic sells)
6. **Add position state integration** for RESET detection
7. **Track compound growth** through cycles
8. **Enhance phase detection** based on window composition

## Priority Recommendations

**High Priority**:
- Add stop-loss order support (OrderType.STOP_LOSS_SELL)
- Implement dual window management

**Medium Priority**:
- Fix order replacement logic
- Add proper window sliding

**Low Priority**:
- Add compound growth tracking
- Enhance logging