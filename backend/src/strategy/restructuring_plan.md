# HyperTrader Restructuring Plan - Step by Step Implementation Guide

## Overview
This document provides a systematic, step-by-step plan to restructure the HyperTrader codebase to address all issues identified in the analysis documents and implement an optimal architecture for the Long Wallet strategy.

## Pre-Restructuring Checklist
- [ ] Create a new git branch: `feature/restructure-long-wallet`
- [ ] Backup current working code
- [ ] Ensure all tests are passing (if any exist)
- [ ] Document current order IDs and positions

---

## Phase 1: Create New Data Models (No Breaking Changes)

### Step 1.1: Create `data_models.py`
**File**: `backend/src/strategy/data_models.py`

1. Create new file with all data structures
2. Add proper OrderType enum:
```python
from enum import Enum
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict

class OrderType(Enum):
    STOP_LOSS_SELL = "stop_loss_sell"  # Stop-loss for long positions
    LIMIT_BUY = "limit_buy"            # Limit buy order
    MARKET_BUY = "market_buy"          # Market buy for entry
    MARKET_SELL = "market_sell"        # Market sell for emergency

class Phase(Enum):
    ADVANCE = "advance"          # 100% long, all stop-losses
    RETRACEMENT = "retracement"  # Mixed position
    DECLINE = "decline"          # 100% cash, all limit buys
    RECOVER = "recover"          # Mixed position returning
    RESET = "reset"             # Transitioning to new cycle

class ExecutionStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
```

3. Add PositionState with proper fields:
```python
@dataclass
class PositionState:
    # Core position data
    entry_price: Decimal
    unit_size_usd: Decimal
    asset_size: Decimal
    position_value_usd: Decimal
    
    # Original values for fragment calculation
    original_asset_size: Decimal
    original_position_value_usd: Decimal
    
    # Fragments (25% each)
    long_fragment_asset: Decimal  # For stop-loss sells
    long_fragment_usd: Decimal    # For limit buys
    
    # Cycle tracking for RESET
    cycle_number: int = 0
    cycle_start_value: Decimal = Decimal("0")
    cumulative_growth: Decimal = Decimal("1.0")
```

4. Add WindowState for tracking:
```python
@dataclass
class WindowState:
    stop_loss_orders: List[int] = field(default_factory=list)
    limit_buy_orders: List[int] = field(default_factory=list)
    
    def total_orders(self) -> int:
        return len(self.stop_loss_orders) + len(self.limit_buy_orders)
    
    def is_all_stop_losses(self) -> bool:
        return len(self.stop_loss_orders) == 4 and len(self.limit_buy_orders) == 0
    
    def is_all_limit_buys(self) -> bool:
        return len(self.limit_buy_orders) == 4 and len(self.stop_loss_orders) == 0
```

### Step 1.2: Update Imports
1. Update `position_map.py` to import from `data_models.py`
2. Update `unit_tracker.py` to import from `data_models.py`
3. Update `main.py` to import from `data_models.py`
4. Run code to ensure imports work

---

## Phase 2: Create Strategy Engine

### Step 2.1: Create `strategy_engine.py`
**File**: `backend/src/strategy/strategy_engine.py`

1. Create new file for all strategy logic:
```python
from decimal import Decimal
from typing import Optional, Tuple, List
from .data_models import Phase, OrderType, WindowState, PositionState

class LongWalletStrategy:
    """Encapsulates all long wallet strategy logic"""
    
    def __init__(self, position_state: PositionState):
        self.position_state = position_state
        self.current_phase = Phase.ADVANCE
        self.windows = WindowState()
```

2. Move phase detection logic from `unit_tracker.py`:
```python
def detect_phase(self, windows: WindowState) -> Phase:
    """Determine current phase based on window composition"""
    if windows.is_all_stop_losses():
        return Phase.ADVANCE
    elif windows.is_all_limit_buys():
        return Phase.DECLINE
    elif len(windows.stop_loss_orders) > 0 and len(windows.limit_buy_orders) > 0:
        # Mixed state - determine if RETRACEMENT or RECOVER
        if self.current_phase in [Phase.ADVANCE, Phase.RETRACEMENT]:
            return Phase.RETRACEMENT
        else:
            return Phase.RECOVER
    return self.current_phase
```

3. Add order replacement logic:
```python
def get_replacement_order(self, 
                         executed_unit: int, 
                         current_unit: int, 
                         executed_type: OrderType) -> Tuple[int, OrderType]:
    """Determine replacement order when one executes"""
    if executed_type == OrderType.STOP_LOSS_SELL:
        # Stop-loss triggered -> Place limit buy at current+1
        return (current_unit + 1, OrderType.LIMIT_BUY)
    elif executed_type == OrderType.LIMIT_BUY:
        # Limit buy filled -> Place stop-loss at current-1
        return (current_unit - 1, OrderType.STOP_LOSS_SELL)
```

4. Add window sliding logic:
```python
def calculate_window_slide(self, 
                          current_unit: int, 
                          direction: str, 
                          phase: Phase) -> Tuple[Optional[int], Optional[int]]:
    """Calculate which orders to add/remove when sliding window"""
    if direction == 'up' and phase == Phase.ADVANCE:
        new_order = current_unit - 1  # Add stop-loss
        old_order = current_unit - 5  # Remove stop-loss
        return (new_order, old_order)
    elif direction == 'down' and phase == Phase.DECLINE:
        new_order = current_unit + 1  # Add limit buy
        old_order = current_unit + 5  # Remove limit buy
        return (new_order, old_order)
    return (None, None)
```

5. Add RESET detection:
```python
def should_reset(self, windows: WindowState, phase: Phase) -> bool:
    """Check if RESET conditions are met"""
    # Reset when returning to 100% long from mixed phases
    if phase == Phase.RECOVER and windows.is_all_stop_losses():
        return True
    if phase == Phase.RETRACEMENT and windows.is_all_stop_losses():
        return True
    return False
```

---

## Phase 3: Create Order Manager

### Step 3.1: Create `order_manager.py`
**File**: `backend/src/strategy/order_manager.py`

1. Create order management layer:
```python
from decimal import Decimal
from typing import Optional, Dict, List
from .data_models import OrderType, PositionConfig, ExecutionStatus

class OrderManager:
    """Manages all order operations"""
    
    def __init__(self, sdk_client, symbol: str):
        self.sdk_client = sdk_client
        self.symbol = symbol
        self.active_orders: Dict[str, PositionConfig] = {}
```

2. Add order placement methods:
```python
async def place_stop_loss_order(self, 
                                unit: int, 
                                trigger_price: Decimal, 
                                size: Decimal) -> Optional[str]:
    """Place a stop-loss sell order"""
    result = await self.sdk_client.place_stop_order(
        symbol=self.symbol,
        is_buy=False,
        size=size,
        trigger_price=trigger_price,
        reduce_only=True
    )
    
    if result.success:
        self.active_orders[result.order_id] = PositionConfig(
            unit=unit,
            price=trigger_price,
            order_id=result.order_id,
            order_type=OrderType.STOP_LOSS_SELL,
            execution_status=ExecutionStatus.PENDING
        )
        return result.order_id
    return None

async def place_limit_buy_order(self, 
                               unit: int, 
                               price: Decimal, 
                               size: Decimal) -> Optional[str]:
    """Place a limit buy order"""
    result = await self.sdk_client.place_limit_order(
        symbol=self.symbol,
        is_buy=True,
        price=price,
        size=size,
        reduce_only=False,
        post_only=True
    )
    
    if result.success:
        self.active_orders[result.order_id] = PositionConfig(
            unit=unit,
            price=price,
            order_id=result.order_id,
            order_type=OrderType.LIMIT_BUY,
            execution_status=ExecutionStatus.PENDING
        )
        return result.order_id
    return None
```

3. Add order cancellation:
```python
async def cancel_order(self, order_id: str) -> bool:
    """Cancel an active order"""
    success = await self.sdk_client.cancel_order(self.symbol, order_id)
    if success and order_id in self.active_orders:
        self.active_orders[order_id].execution_status = ExecutionStatus.CANCELLED
        del self.active_orders[order_id]
    return success
```

4. Add fill handling:
```python
def handle_order_fill(self, order_id: str, filled_price: Decimal, filled_size: Decimal):
    """Process an order fill"""
    if order_id in self.active_orders:
        config = self.active_orders[order_id]
        config.mark_filled(filled_price, filled_size)
        return config
    return None
```

---

## Phase 4: Create Position Tracker

### Step 4.1: Create `position_tracker.py`
**File**: `backend/src/strategy/position_tracker.py`

1. Create position tracking layer:
```python
from decimal import Decimal
from datetime import datetime
from typing import Optional
from .data_models import PositionState, Phase

class PositionTracker:
    """Tracks position state and unit movements"""
    
    def __init__(self, position_state: PositionState, unit_size_usd: Decimal):
        self.position_state = position_state
        self.unit_size_usd = unit_size_usd
        self.current_unit = 0
        self.peak_unit = 0
        self.valley_unit = 0
```

2. Add unit boundary detection:
```python
def check_unit_change(self, current_price: Decimal) -> Optional[int]:
    """Check if price has crossed a unit boundary"""
    # Calculate which unit we're in
    units_from_entry = (current_price - self.position_state.entry_price) / self.unit_size_usd
    new_unit = int(units_from_entry)
    
    if new_unit != self.current_unit:
        old_unit = self.current_unit
        self.current_unit = new_unit
        
        # Update peak/valley
        if new_unit > self.peak_unit:
            self.peak_unit = new_unit
        if new_unit < self.valley_unit:
            self.valley_unit = new_unit
            
        return new_unit
    return None
```

3. Add compound growth tracking:
```python
def calculate_compound_growth(self, current_position_value: Decimal) -> Decimal:
    """Calculate compound growth factor"""
    return current_position_value / self.position_state.original_position_value_usd

def reset_for_new_cycle(self, new_position_value: Decimal, new_asset_size: Decimal):
    """Reset tracking for new cycle after RESET"""
    # Update growth metrics
    growth_factor = self.calculate_compound_growth(new_position_value)
    self.position_state.cumulative_growth *= growth_factor
    self.position_state.cycle_number += 1
    
    # Reset to new baseline
    self.position_state.original_position_value_usd = new_position_value
    self.position_state.original_asset_size = new_asset_size
    
    # Recalculate fragments
    self.position_state.long_fragment_asset = new_asset_size / 4
    self.position_state.long_fragment_usd = new_position_value / 4
    
    # Reset units
    self.current_unit = 0
    self.peak_unit = 0
    self.valley_unit = 0
```

---

## Phase 5: Refactor Main.py

### Step 5.1: Simplify main.py to orchestration only
**File**: `backend/src/main.py`

1. Update imports:
```python
from strategy.data_models import Phase, OrderType, PositionState, WindowState
from strategy.strategy_engine import LongWalletStrategy
from strategy.order_manager import OrderManager
from strategy.position_tracker import PositionTracker
```

2. Simplify initialization:
```python
class HyperTrader:
    def __init__(self, symbol: str = "ETH", use_testnet: bool = True):
        self.symbol = symbol
        self.use_testnet = use_testnet
        
        # Components (initialized in initialize())
        self.strategy_engine: Optional[LongWalletStrategy] = None
        self.order_manager: Optional[OrderManager] = None
        self.position_tracker: Optional[PositionTracker] = None
```

3. Refactor price update handler:
```python
async def _handle_price_update(self, price: Decimal):
    """Handle price updates using new components"""
    # Check for unit change
    new_unit = self.position_tracker.check_unit_change(price)
    
    if new_unit is not None:
        # Get current phase
        phase = self.strategy_engine.detect_phase(self.strategy_engine.windows)
        
        # Check for window sliding
        direction = 'up' if new_unit > self.position_tracker.current_unit else 'down'
        new_order, old_order = self.strategy_engine.calculate_window_slide(
            new_unit, direction, phase
        )
        
        if old_order:
            await self._cancel_order_at_unit(old_order)
        if new_order:
            await self._place_order_at_unit(new_order, phase)
```

4. Refactor order fill handler:
```python
async def handle_order_fill(self, order_id: str, filled_price: Decimal, filled_size: Decimal):
    """Handle order fills using new components"""
    # Update order manager
    filled_config = self.order_manager.handle_order_fill(order_id, filled_price, filled_size)
    
    if filled_config:
        # Get replacement order from strategy
        replacement_unit, replacement_type = self.strategy_engine.get_replacement_order(
            filled_config.unit,
            self.position_tracker.current_unit,
            filled_config.order_type
        )
        
        # Place replacement order
        await self._place_order(replacement_unit, replacement_type)
        
        # Check for RESET
        phase = self.strategy_engine.detect_phase(self.strategy_engine.windows)
        if self.strategy_engine.should_reset(self.strategy_engine.windows, phase):
            await self._handle_reset()
```

5. Implement clean RESET:
```python
async def _handle_reset(self):
    """Handle RESET using new components"""
    # Get current position
    positions = self.sdk_client.get_positions()
    position = positions[self.symbol]
    
    # Calculate new values
    new_value = position.size * self.current_price
    
    # Reset position tracker
    self.position_tracker.reset_for_new_cycle(new_value, position.size)
    
    # Cancel all orders
    for order_id in list(self.order_manager.active_orders.keys()):
        await self.order_manager.cancel_order(order_id)
    
    # Reinitialize windows
    await self._initialize_windows()
```

---

## Phase 6: Update Existing Files

### Step 6.1: Refactor position_map.py
1. Remove business logic functions (move to strategy_engine.py)
2. Keep only position map data structure management
3. Remove `handle_order_replacement` (now in strategy_engine.py)
4. Keep helper functions like `add_unit_level`

### Step 6.2: Refactor unit_tracker.py
1. Remove phase detection (moved to strategy_engine.py)
2. Remove window management (moved to strategy_engine.py)
3. Keep only unit tracking functionality
4. Merge useful parts into position_tracker.py

### Step 6.3: Clean up imports and remove circular dependencies
1. Ensure no file imports from main.py
2. Ensure data_models.py has no imports from other strategy files
3. Verify each module has a single responsibility

---

## Phase 7: Testing and Validation

### Step 7.1: Create Unit Tests
1. Test strategy_engine phase detection
2. Test order_manager order placement
3. Test position_tracker unit boundary detection
4. Test RESET mechanism

### Step 7.2: Integration Testing
1. Test full order cycle (place → fill → replace)
2. Test phase transitions
3. Test window sliding in both directions
4. Test RESET with compound growth

### Step 7.3: Validation Checklist
- [ ] All stop-losses use OrderType.STOP_LOSS_SELL
- [ ] All buys use OrderType.LIMIT_BUY
- [ ] Windows track correctly (stop_loss_orders and limit_buy_orders)
- [ ] Phase transitions work correctly
- [ ] RESET captures compound growth
- [ ] No circular dependencies
- [ ] Each module has single responsibility

---

## Phase 8: Configuration and Constants

### Step 8.1: Create `config.py`
**File**: `backend/src/strategy/config.py`

```python
from decimal import Decimal

class LongWalletConfig:
    # Window sizes
    WINDOW_SIZE = 4
    WINDOW_TRAIL_DISTANCE = 4
    
    # Fragment sizes
    FRAGMENT_PERCENT = Decimal("0.25")  # 25%
    
    # Order settings
    POST_ONLY = True  # Maker orders only
    REDUCE_ONLY_STOPS = True  # Stop-losses reduce only
    
    # Risk settings
    MAX_POSITION_SIZE = Decimal("10000")  # USD
    MIN_ORDER_SIZE = Decimal("10")  # USD
```

### Step 8.2: Update all hardcoded values
1. Replace magic number 4 with WINDOW_SIZE
2. Replace 0.25 with FRAGMENT_PERCENT
3. Use config for all settings

---

## Migration Sequence

### Week 1: Data Models and Strategy Engine
1. Day 1-2: Create data_models.py
2. Day 3-4: Create strategy_engine.py
3. Day 5: Test strategy logic independently

### Week 2: Order and Position Management
1. Day 1-2: Create order_manager.py
2. Day 3-4: Create position_tracker.py
3. Day 5: Integration testing

### Week 3: Main Refactor and Cleanup
1. Day 1-2: Refactor main.py
2. Day 3: Update position_map.py
3. Day 4: Update unit_tracker.py
4. Day 5: Full system testing

### Week 4: Polish and Deploy
1. Day 1-2: Add comprehensive logging
2. Day 3: Add error recovery
3. Day 4: Performance testing
4. Day 5: Deploy to testnet

---

## Success Criteria

### Functional Requirements
- [ ] Stop-loss orders trigger correctly at or below price
- [ ] Limit buy orders execute at exact price
- [ ] Windows slide correctly in both directions
- [ ] Phase transitions occur at right times
- [ ] RESET captures compound growth
- [ ] Orders replace correctly based on type

### Non-Functional Requirements
- [ ] No circular dependencies
- [ ] Each module < 300 lines
- [ ] Clear separation of concerns
- [ ] All business logic in strategy_engine
- [ ] All order logic in order_manager
- [ ] Main.py is purely orchestration

### Testing Requirements
- [ ] Unit tests for each module
- [ ] Integration tests for full cycle
- [ ] Edge case handling
- [ ] Error recovery tested
- [ ] Performance benchmarks met

---

## Rollback Plan

If issues arise during migration:

1. **Immediate Rollback**: Git revert to previous commit
2. **Partial Rollback**: Keep data_models.py, revert other changes
3. **Gradual Migration**: Implement one module at a time
4. **Parallel Running**: Run new and old code side-by-side

---

## Post-Migration Tasks

1. **Documentation**: Update all documentation with new structure
2. **Monitoring**: Add metrics for each component
3. **Performance**: Optimize hot paths
4. **Hedge Wallet**: Plan integration using same structure
5. **Code Review**: Get external review of new architecture

---

## Notes and Warnings

### Critical Points
- Never mix stop-loss and limit orders in same window
- Always maintain exactly 4 orders per window
- RESET must recalculate fragments based on new position size
- Phase detection depends on window composition, not time

### Common Pitfalls
- Forgetting to update fragments after RESET
- Using wrong order type for replacements
- Not tracking compound growth correctly
- Missing unit boundary due to rounding

### Dependencies
- Requires SDK version that supports stop orders
- WebSocket must provide real-time fills
- Position data must be accurate

This plan provides a systematic approach to restructuring the codebase while maintaining functionality and improving maintainability.