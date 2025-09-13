# Sliding Window Implementation - Detailed Specification

## Current Issues

The current implementation has fundamental problems:
1. **Only current-1 stop-loss is trailing properly** - Other 3 stop-losses remain static
2. **Mixed tracking in WindowState** - Uses `sell_orders` and `buy_orders` lists but doesn't maintain them properly
3. **Incorrect sliding logic in `_slide_window()`** - Checks window composition instead of maintaining separate lists
4. **No proper list-based tracking** - Missing the core `trailing_stop` and `trailing_buy` lists

## Desired Data Structure

### Core Components

#### 1. Position Map (`self.position_map: Dict[int, PositionConfig]`)
```python
# Built after initial entry with actual fill price
# Keys: -10 to +10 (21 total units)
# Values: PositionConfig objects containing:
#   - unit: int
#   - price: Decimal (calculated from entry_price ± unit * unit_size_usd)
#   - order_id: Optional[str]
#   - order_type: Optional[OrderType]
#   - status: ExecutionStatus
```

#### 2. Two Tracking Lists (NEW - Replace WindowState)
```python
# In UnitTracker class or as new SlidingWindow dataclass
self.trailing_stop: List[int] = []     # Units with active stop-loss orders
self.trailing_buy: List[int] = []      # Units with active limit buy orders
self.current_unit: int = 0              # Current price unit level
```

#### 3. Remove/Refactor WindowState
The current `WindowState` dataclass with `sell_orders` and `buy_orders` should be:
- **Option A**: Renamed to use `trailing_stop` and `trailing_buy` 
- **Option B**: Replaced entirely with the two lists above

## Detailed Sliding Window Behavior

### Initial Setup (After Position Entry)
```python
# Starting at unit 0 after entry
self.current_unit = 0
self.trailing_stop = [-4, -3, -2, -1]  # Place 4 stop-loss orders
self.trailing_buy = []                  # No buy orders initially

# Place actual orders in Hyperliquid for each unit in trailing_stop
for unit in self.trailing_stop:
    price = self.position_map[unit].price
    place_stop_loss_order(unit, price)
```

### Moving UP (Price Increases, Unit Increases)

**Example: current_unit changes from 0 to 1**

```python
def handle_unit_move_up():
    # 1. Add new stop-loss at current_unit - 1
    new_stop_unit = self.current_unit - 1  # = 0
    self.trailing_stop.append(new_stop_unit)
    place_stop_loss_order(new_stop_unit, self.position_map[new_stop_unit].price)
    
    # 2. Cancel oldest stop-loss (at current_unit - 5)
    old_stop_unit = self.current_unit - 5  # = -4
    if old_stop_unit in self.trailing_stop:
        self.trailing_stop.remove(old_stop_unit)  # or pop(0) since it's the first
        cancel_order(self.position_map[old_stop_unit].order_id)
    
    # Result: trailing_stop = [-3, -2, -1, 0]
```

### Moving DOWN (Price Decreases, Unit Decreases)

**Example: current_unit changes from 1 to 0**

```python
def handle_unit_move_down():
    # 1. Stop-loss at unit 0 triggers automatically in Hyperliquid
    # 2. Remove triggered stop from our list
    if self.current_unit in self.trailing_stop:
        self.trailing_stop.remove(self.current_unit)
    
    # 3. Add limit buy at current_unit + 1
    new_buy_unit = self.current_unit + 1  # = 1
    self.trailing_buy.insert(0, new_buy_unit)  # Add to front
    place_limit_buy_order(new_buy_unit, self.position_map[new_buy_unit].price)
    
    # Result: trailing_stop = [-3, -2, -1], trailing_buy = [1]
```

### Continuing DOWN (Multiple Units)

**From unit 0 → -1 → -2 → -3**

```python
# Each move down:
# - Stop triggers and is removed from trailing_stop
# - New buy added to trailing_buy
# After reaching unit -3:
self.trailing_stop = []  # All stops triggered
self.trailing_buy = [-2, -1, 0, 1]  # 4 buy orders
```

### Further DOWN (Beyond Initial Range)

**From unit -3 to -4**

```python
def handle_deep_decline():
    # 1. Add new buy at current_unit + 1
    new_buy_unit = self.current_unit + 1  # = -3
    self.trailing_buy.insert(0, new_buy_unit)
    place_limit_buy_order(new_buy_unit, self.position_map[new_buy_unit].price)
    
    # 2. Cancel oldest buy (at current_unit + 5)
    old_buy_unit = self.current_unit + 5  # = 1
    if old_buy_unit in self.trailing_buy:
        self.trailing_buy.remove(old_buy_unit)  # Remove from end
        cancel_order(self.position_map[old_buy_unit].order_id)
    
    # Result: trailing_buy = [-3, -2, -1, 0]
```

### Recovery (Buy Orders Fill)

**When price rises and buy at unit -3 fills**

```python
def handle_buy_fill(filled_unit):
    # 1. Remove from trailing_buy
    if filled_unit in self.trailing_buy:
        self.trailing_buy.remove(filled_unit)
    
    # 2. Add new stop-loss
    self.trailing_stop.append(filled_unit)
    # No need to place order - we're now long at this unit
    
    # Result: trailing_stop = [-3], trailing_buy = [-2, -1, 0]
```

## Files and Functions to Change

### 1. **data_models.py**
```python
# REMOVE or REFACTOR WindowState class
@dataclass
class WindowState:
    sell_orders: List[int] = field(default_factory=list)  # RENAME to trailing_stop
    buy_orders: List[int] = field(default_factory=list)   # RENAME to trailing_buy

# OR ADD NEW:
@dataclass  
class SlidingWindow:
    trailing_stop: List[int] = field(default_factory=list)
    trailing_buy: List[int] = field(default_factory=list)
```

### 2. **unit_tracker.py**
```python
class UnitTracker:
    def __init__(self):
        # CHANGE:
        self.window = WindowState()  # REMOVE or change to SlidingWindow
        
        # ADD:
        self.trailing_stop: List[int] = []
        self.trailing_buy: List[int] = []
    
    # REMOVE these methods that use wrong logic:
    def handle_stop_loss_execution()  # Current logic is wrong
    def handle_limit_buy_execution()  # Current logic is wrong
    
    # ADD new methods:
    def add_trailing_stop(self, unit: int)
    def remove_trailing_stop(self, unit: int)
    def add_trailing_buy(self, unit: int)
    def remove_trailing_buy(self, unit: int)
```

### 3. **main.py - Complete Rewrite of Window Logic**

```python
# REMOVE this entire function - it uses wrong logic:
async def _slide_window(self, direction: str):
    # DELETE ALL - checking window_state['sell_orders'] >= 2 is wrong
    
# REPLACE with:
async def _slide_window(self, direction: str):
    """Properly slide window using list-based tracking"""
    if direction == 'up':
        await self._slide_window_up()
    elif direction == 'down':
        await self._slide_window_down()

async def _slide_window_up(self):
    """Handle upward price movement"""
    # Add stop at current-1
    new_stop = self.unit_tracker.current_unit - 1
    if new_stop not in self.unit_tracker.trailing_stop:
        self.unit_tracker.trailing_stop.append(new_stop)
        await self._place_stop_loss_order(new_stop)
    
    # Cancel stop at current-5
    old_stop = self.unit_tracker.current_unit - 5
    if old_stop in self.unit_tracker.trailing_stop:
        self.unit_tracker.trailing_stop.remove(old_stop)
        await self._cancel_order(old_stop)

async def _slide_window_down(self):
    """Handle downward price movement"""
    # Stop-loss already triggered, remove from list
    current = self.unit_tracker.current_unit
    if current in self.unit_tracker.trailing_stop:
        self.unit_tracker.trailing_stop.remove(current)
    
    # Add buy at current+1
    new_buy = current + 1
    if new_buy not in self.unit_tracker.trailing_buy:
        self.unit_tracker.trailing_buy.insert(0, new_buy)
        await self._place_limit_buy_order(new_buy)
    
    # If we have 5+ buys, cancel the oldest
    if len(self.unit_tracker.trailing_buy) > 4:
        old_buy = self.unit_tracker.trailing_buy.pop()
        await self._cancel_order(old_buy)

# CHANGE _place_window_orders():
async def _place_window_orders(self):
    """Place initial 4 stop-loss orders"""
    # REMOVE: window_state = self.unit_tracker.get_window_state()
    
    # ADD:
    self.unit_tracker.trailing_stop = [-4, -3, -2, -1]
    self.unit_tracker.trailing_buy = []
    
    for unit in self.unit_tracker.trailing_stop:
        await self._place_stop_loss_order(unit)
```

### 4. **Remove Zombie Code**

#### In position_map.py:
```python
# REMOVE these deprecated functions entirely:
def update_sliding_window()  # Already marked deprecated
def get_window_orders()      # Uses wrong window_type approach
```

#### In strategy_engine.py:
```python
# REMOVE or REFACTOR:
def calculate_window_slide()  # Uses WindowState wrong
def _initialize_windows()     # Sets window.sell_orders wrong
```

#### In PositionConfig (data_models.py):
```python
# REMOVE these fields - they're not used correctly:
window_type: Optional[str] = None   # DELETE
window_index: Optional[int] = None  # DELETE
in_window: bool = False             # DELETE if exists
```

## Order Fill Handlers

### Stop-Loss Fill
```python
async def handle_order_fill(self, order_id: str, filled_price: Decimal, filled_size: Decimal):
    filled_unit = self._find_unit_by_order_id(order_id)
    
    if filled_unit in self.unit_tracker.trailing_stop:
        # Stop-loss executed
        self.unit_tracker.trailing_stop.remove(filled_unit)
        
        # Add replacement buy at unit+1
        replacement_unit = filled_unit + 1
        if replacement_unit not in self.unit_tracker.trailing_buy:
            self.unit_tracker.trailing_buy.insert(0, replacement_unit)
            await self._place_limit_buy_order(replacement_unit)
```

### Limit Buy Fill
```python
    elif filled_unit in self.unit_tracker.trailing_buy:
        # Buy executed
        self.unit_tracker.trailing_buy.remove(filled_unit)
        
        # Add replacement stop at unit-1
        replacement_unit = filled_unit - 1
        if replacement_unit not in self.unit_tracker.trailing_stop:
            self.unit_tracker.trailing_stop.append(replacement_unit)
            await self._place_stop_loss_order(replacement_unit)
```

## Testing the Implementation

1. **Initial State**: Verify trailing_stop = [-4,-3,-2,-1], trailing_buy = []
2. **Move Up to 1**: Verify trailing_stop = [-3,-2,-1,0], order at -4 cancelled
3. **Move Down to 0**: Verify stop at 0 triggers, trailing_stop = [-3,-2,-1], trailing_buy = [1]
4. **Continue to -3**: Verify trailing_stop = [], trailing_buy = [-2,-1,0,1]
5. **Move to -4**: Verify trailing_buy = [-3,-2,-1,0], order at 1 cancelled
6. **Recovery to -3**: Verify buy fills, trailing_stop = [-3], trailing_buy = [-2,-1,0]

## Critical Points

1. **Lists are the source of truth** - Not the position_map flags
2. **Always maintain exactly 4 total orders** between both lists
3. **Never duplicate orders** - Check list membership before adding
4. **Order of operations matters**:
   - On UP: Add new stop THEN cancel old
   - On DOWN: Remove triggered stop THEN add new buy
5. **Position map is for prices only** - Lists track what's active

## Summary

The core issue is that the current code tries to determine behavior based on window composition (`if len(window_state['sell_orders']) >= 2`) instead of maintaining proper trailing lists. The fix requires:

1. Replace WindowState with proper trailing_stop/trailing_buy lists
2. Rewrite _slide_window() to use list operations
3. Remove all zombie code that uses old window tracking
4. Ensure order fills update the lists correctly

This will make the sliding window behave exactly as specified: trailing stop-losses when advancing, converting to trailing buys when declining, always maintaining 4 total orders.