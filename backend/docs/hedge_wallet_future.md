# Hedge Wallet Future Implementation

## Overview
This document consolidates all hedge wallet specific requirements from the v9.4.12 strategy document for future implementation. The hedge wallet operates as a separate strategy with unique order management, position transitions, and window sliding logic.

## Core Hedge Wallet Concept

### Position Rotation Cycle
The hedge wallet transitions through distinct position states:
**Long → Cash → Short → Cash → Long**

This is fundamentally different from the long wallet which maintains fragments and never goes fully to cash or short.

## Required Components

### 1. Order Types (position_map.py)
```python
class OrderType(Enum):
    # Hedge-specific orders
    STOP_LOSS_FULL = "stop_loss_full"         # 100% position exit
    STOP_ENTRY_SHORT = "stop_entry_short"     # Enter short on price drop
    STOP_LOSS_COVER = "stop_loss_cover"       # Exit short on price rise
    MARKET_BUY_FULL = "market_buy_full"       # Re-enter long with all cash
```

### 2. Window Management (unit_tracker.py)
```python
@dataclass
class HedgeWalletWindows:
    stop_loss_full_long: Optional[int] = None           # Single order at current-1
    enter_short_orders: List[int] = field(default_factory=list)    # 4 stop-entry shorts
    stop_loss_orders_hedge: List[int] = field(default_factory=list) # Dynamic stops for shorts
    market_buy_pending: bool = False                    # Flag for full long re-entry
```

### 3. Position State Tracking (position_map.py)
```python
@dataclass
class HedgePositionState:
    # Full position transitions (not fragments)
    hedge_full_position_asset: Decimal  # 100% for initial exit
    
    # Short position specifics
    is_short: bool = False
    short_entry_prices: List[Decimal] = field(default_factory=list)
    short_sizes: List[Decimal] = field(default_factory=list)
    total_short_size: Decimal = Decimal("0")
    
    # Fragment values for shorts
    hedge_fragment_usd: Decimal         # 25% for each short entry
    hedge_fragment_asset: Decimal       # 25% for covering shorts
```

## Hedge Wallet Phases

### ADVANCE Phase (Hedge)
- **State**: 100% long with stop-loss ready
- **Orders**: 
  - 1 `stop_loss_full_long` at current-1 (100% position)
  - 4 `enter_short_orders` at [current-1, current-2, current-3, current-4]
- **Window Sliding**: As price rises, both windows trail upward
- **Transition**: To RETRACEMENT when price falls and triggers stop_loss_full_long

### RETRACEMENT Phase (Hedge)
- **State**: Cash transitioning to short
- **Orders**: Mix of stop-entry shorts and stop-loss covers
- **Actions**:
  - Stop-entry short triggers → Add stop-loss cover at current+1
  - Stop-loss cover triggers → Add stop-entry short at current-1
- **Transitions**:
  - To DECLINE: All 4 stop-entry shorts triggered
  - To RESET: All stop-losses triggered (100% cash)

### DECLINE Phase (Hedge)
- **State**: Maximum short exposure
- **Orders**: 4 stop-loss covers at [current+1, current+2, current+3, current+4]
- **Window Sliding**: As price falls, stop-losses trail downward
- **Transition**: To RECOVER when first stop-loss cover triggers

### RECOVERY Phase (Hedge)
- **State**: Partially covered shorts
- **Orders**: Mix of stop-loss covers and stop-entry shorts
- **Transitions**:
  - To RESET: All shorts covered (100% cash)
  - To DECLINE: All stop-entry shorts triggered again

### RESET Phase (Hedge)
- **State**: 100% cash with profits from short cycle
- **Actions**:
  1. Place market buy order with all cash (original + profits)
  2. Reset unit counters to 0
  3. Reinitialize windows for new cycle
- **Result**: Returns to ADVANCE with compounded position

## Implementation Requirements

### Order Placement Logic (main.py)
```python
async def _initialize_hedge_wallet_position(self):
    # Place stop_loss_full_long at current-1 for 100% position
    await self._place_stop_loss_full(self.current_unit - 1)
    
    # Place 4 stop-entry short orders
    for i in range(1, 5):
        await self._place_stop_entry_short(self.current_unit - i)

async def _place_stop_loss_full(self, unit: int):
    # Exit entire long position
    size = self.position_state.asset_size  # 100%
    
async def _place_stop_entry_short(self, unit: int):
    # Open short position when price falls to trigger
    size_usd = self.position_state.hedge_fragment_usd  # 25%
    
async def _place_stop_loss_cover(self, unit: int):
    # Cover short position when price rises to trigger
    size_asset = self.position_state.hedge_fragment_asset  # 25% of short
```

### Window Sliding Logic (unit_tracker.py)
```python
def _slide_hedge_windows(self, direction: str):
    if self.phase == Phase.ADVANCE:
        # Slide both stop_loss_full_long and enter_short_orders
        self.windows.stop_loss_full_long = self.current_unit - 1
        self.windows.enter_short_orders = [
            self.current_unit - i for i in range(1, 5)
        ]
    
    elif self.phase == Phase.DECLINE:
        # Slide stop_loss_orders_hedge
        self.windows.stop_loss_orders_hedge = [
            self.current_unit + i for i in range(1, 5)
        ]
```

### Order Execution Handling (main.py)
```python
async def _handle_hedge_wallet_fill(self, order_id: str, order_type: str):
    if order_type == "stop_loss_full":
        # Entire long position sold, now in cash
        self.position_state.is_short = False
        # Short entry orders now active
        
    elif order_type == "stop_entry_short":
        # Short position opened
        self.position_state.is_short = True
        # Place stop-loss cover at current+1
        await self._place_stop_loss_cover(self.current_unit + 1)
        
    elif order_type == "stop_loss_cover":
        # Short position covered
        covered_index = self._get_covered_index(order_id)
        self.position_state.short_sizes[covered_index] = Decimal("0")
        
        if all(s == 0 for s in self.position_state.short_sizes):
            # All shorts covered, trigger RESET
            await self._handle_hedge_reset()
```

### RESET Mechanism (main.py)
```python
async def _handle_hedge_reset(self):
    # Calculate total cash including short profits
    total_cash = self._calculate_total_cash_with_profits()
    
    # Place market buy with all cash
    await self._place_market_buy_full(total_cash)
    
    # Reset unit tracking
    self.unit_tracker.reset_for_new_cycle(self.current_price)
    
    # Reinitialize hedge windows
    await self._initialize_hedge_wallet_position()
```

## Key Differences from Long Wallet

1. **Position Transitions**: Full position changes vs fragments
2. **Order Types**: Stop-entry shorts and full exits vs partial limit orders
3. **Window Structure**: Multiple distinct windows vs two similar windows
4. **RESET Trigger**: After covering all shorts vs returning to 100% long
5. **Profit Capture**: Through short cycles vs gradual accumulation

## Testing Considerations

1. **Short Position Mechanics**: Verify stop-entry orders correctly open shorts
2. **Window Coordination**: Ensure all four windows operate independently
3. **RESET Compounding**: Validate profit capture and reinvestment
4. **Phase Transitions**: Test all possible phase paths
5. **Order Conflicts**: Prevent position netting issues

## Future Enhancements

1. **Dynamic Fragment Sizing**: Adjust based on volatility
2. **Risk Management**: Add maximum short exposure limits
3. **Profit Taking**: Partial profit taking during short cycles
4. **Correlation Trading**: Coordinate with long wallet signals
5. **Market Condition Adaptation**: Adjust strategy based on trend strength