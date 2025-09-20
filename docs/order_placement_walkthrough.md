# Order Placement Walkthrough

## Overview
This document traces the complete flow of order placement and management in the HyperTrader system, from initial position entry through all market scenarios.

## Core Components

### Files Involved
- **backend/src/main.py** - Main trading loop and order execution
- **backend/src/strategy/unit_tracker.py** - Unit tracking and phase detection
- **backend/src/strategy/position_map.py** - Unit price calculations
- **backend/src/exchange/hyperliquid_client.py** - Exchange API interactions
- **backend/src/strategy/data_models.py** - Order and position data structures

## Order Types
- **STOP_LOSS_SELL**: Stop order to sell when price drops (placed below current price)
- **STOP_BUY**: Stop order to buy when price rises (placed above current price)

## Key Data Structures

### Trailing Lists (backend/src/strategy/unit_tracker.py)
```python
self.trailing_stop: List[int] = [-4, -3, -2, -1]  # Stop-loss orders below price
self.trailing_buy: List[int] = []                  # Buy orders above price
```

### Phase Detection
- **ADVANCE**: 4 stops, 0 buys - Price moving up from entry
- **DECLINE**: 0 stops, 4 buys - Price moving down from peak
- **RETRACEMENT**: Mixed state during decline recovery
- **RECOVERY**: Mixed state during advance pullback

## Order Placement Flow

### 1. Initial Entry (backend/src/main.py: _initialize_position)
```python
async def _initialize_position():
    # Check for existing position first
    positions = self.sdk_client.get_positions()

    if self.symbol in positions:
        # Load existing position
        position = positions[self.symbol]
        entry_price = position.entry_price
        asset_size = position.size
    else:
        # Create new position (long wallet only)
        if self.wallet_type == "long":
            result = await self._place_market_order("buy", estimated_size)

            # Wait for position to be fully established
            # Poll for position with timeout
            for attempt in range(10):
                await asyncio.sleep(1)
                positions = self.sdk_client.get_positions()
                if self.symbol in positions:
                    break

            position = positions[self.symbol]
            entry_price = position.entry_price  # Use ACTUAL fill price
            asset_size = position.size  # Use ACTUAL position size

    # Initialize position map with actual values
    self.position_state, self.position_map = calculate_initial_position_map(
        entry_price=entry_price,
        unit_size_usd=self.unit_size_usd,
        asset_size=asset_size,
        position_value_usd=asset_size * entry_price
    )

    # Initialize unit tracker with sliding window
    self.unit_tracker = UnitTracker(
        position_state=self.position_state,
        position_map=self.position_map
    )

    # Place initial sliding window orders
    await self._place_window_orders()
```

**State After Entry:**
- Current unit: 0
- Trailing stops: [-4, -3, -2, -1]  # Set in UnitTracker init
- Trailing buys: []
- Phase: ADVANCE

### 2. Price Movement Detection (backend/src/main.py: _handle_price_update)
```python
def _handle_price_update(self, price: Decimal):
    """Handle price updates from WebSocket"""
    self.current_price = price

    # Check for unit boundary crossing
    unit_event = self.unit_tracker.calculate_unit_change(price)

    if unit_event:
        # Create async task to handle unit change
        asyncio.create_task(self._handle_unit_change(unit_event))
```

### 3. Unit Change Handling (backend/src/main.py: _handle_unit_change)

#### Scenario A: Price Moving UP
**Initial State:** Price crosses up to a new unit

```python
async def _handle_unit_change(event: UnitChangeEvent):
    current_unit = self.unit_tracker.current_unit

    if event.direction == 'up':
        # Place new stop at current_unit - 1
        new_stop_unit = current_unit - 1

        # Ensure unit exists in position map
        if new_stop_unit not in self.position_map:
            add_unit_level(self.position_state, self.position_map, new_stop_unit)

        # Place new stop if not already there
        if new_stop_unit not in self.unit_tracker.trailing_stop:
            order_id = await self._place_stop_loss_order(new_stop_unit)
            if order_id:
                self.unit_tracker.add_trailing_stop(new_stop_unit)

        # Cancel the oldest (furthest) stop if we have more than 4
        if len(self.unit_tracker.trailing_stop) > 4:
            sorted_stops = sorted(self.unit_tracker.trailing_stop)
            oldest_stop = sorted_stops[0]  # Lowest unit

            # Cancel and remove
            if oldest_stop in self.position_map and self.position_map[oldest_stop].is_active:
                success = await self._cancel_order(oldest_stop)
                if success:
                    self.unit_tracker.remove_trailing_stop(oldest_stop)
```

**Result:** Maintains 4 trailing stops, sliding window up

#### Scenario B: Price Moving DOWN
**Initial State:** Price crosses down to a lower unit

```python
    elif event.direction == 'down':
        # Place new buy at current_unit + 1
        new_buy_unit = current_unit + 1

        # Ensure unit exists in position map
        if new_buy_unit not in self.position_map:
            add_unit_level(self.position_state, self.position_map, new_buy_unit)

        # Place new buy if not already there
        if new_buy_unit not in self.unit_tracker.trailing_buy:
            order_id = await self._place_stop_buy_order(new_buy_unit)
            if order_id:
                self.unit_tracker.add_trailing_buy(new_buy_unit)

        # Cancel the oldest (furthest) buy if we have more than 4
        if len(self.unit_tracker.trailing_buy) > 4:
            sorted_buys = sorted(self.unit_tracker.trailing_buy, reverse=True)
            oldest_buy = sorted_buys[0]  # Highest unit

            # Cancel and remove
            if oldest_buy in self.position_map and self.position_map[oldest_buy].is_active:
                success = await self._cancel_order(oldest_buy)
                if success:
                    self.unit_tracker.remove_trailing_buy(oldest_buy)
```

**Result:** Maintains up to 4 trailing buys above current price

### 4. Order Placement Methods

#### Stop Loss Order Placement
```python
async def _place_stop_loss_order(self, unit: int) -> Optional[str]:
    config = self.position_map[unit]

    # Check if order already active at this unit
    if config.is_active:
        return config.order_id

    trigger_price = config.price
    size = self.position_state.long_fragment_asset

    # Place stop order via SDK
    result = await self._sdk_place_stop_order("sell", trigger_price, size)

    if result.success:
        config.set_active_order(result.order_id, OrderType.STOP_LOSS_SELL)
        return result.order_id
    return None
```

#### Stop Buy Order Placement (Adaptive)
```python
async def _place_stop_buy_order(self, unit: int) -> Optional[str]:
    config = self.position_map[unit]
    price = config.price

    # Get current market price
    current_market_price = await self._get_current_price()

    # Use adjusted fragment in recovery phase (includes PnL reinvestment)
    fragment_usd = self.unit_tracker.get_adjusted_fragment_usd()
    size = fragment_usd / price

    if price > current_market_price:
        # Price above market - use STOP BUY
        result = self.sdk_client.place_stop_buy(
            symbol=self.symbol,
            size=size,
            trigger_price=price,
            limit_price=price
        )
    else:
        # Price at/below market - use LIMIT BUY
        result = self.sdk_client.place_limit_order(
            symbol=self.symbol,
            is_buy=True,
            price=price,
            size=size,
            post_only=True  # Maker order to avoid fees
        )

    if result.success:
        config.set_active_order(result.order_id, OrderType.STOP_BUY)
        return result.order_id
    return None
```

### 5. Order Execution Handling (backend/src/main.py: handle_order_fill)

#### Stop Loss Execution
```python
async def handle_order_fill(self, order_id: str, filled_price: Decimal, filled_size: Decimal):
    # Find the unit that was filled
    for unit, config in self.position_map.items():
        if config.order_id == order_id:
            filled_unit = unit
            filled_order_type = config.order_type
            config.mark_filled(filled_price, filled_size)
            break

    if filled_order_type == OrderType.STOP_LOSS_SELL:
        # Remove from trailing_stop list
        self.unit_tracker.remove_trailing_stop(filled_unit)

        # Track realized PnL
        self.unit_tracker.track_realized_pnl(
            sell_price=filled_price,
            buy_price=self.position_state.entry_price,
            size=filled_size
        )

        # Add replacement buy at filled_unit + 1
        replacement_unit = filled_unit + 1
        if replacement_unit not in self.position_map:
            add_unit_level(self.position_state, self.position_map, replacement_unit)

        if self.unit_tracker.add_trailing_buy(replacement_unit):
            order_id = await self._place_stop_buy_order(replacement_unit)
```

#### Stop Buy Execution
```python
    elif filled_order_type == OrderType.STOP_BUY:
        # Remove from trailing_buy list
        self.unit_tracker.remove_trailing_buy(filled_unit)

        # Add replacement stop at filled_unit - 1
        replacement_unit = filled_unit - 1
        if replacement_unit not in self.position_map:
            add_unit_level(self.position_state, self.position_map, replacement_unit)

        if self.unit_tracker.add_trailing_stop(replacement_unit):
            order_id = await self._place_stop_loss_order(replacement_unit)
```

### 6. Window State Tracking

The sliding window state is tracked through list-based management in `UnitTracker`:

```python
class UnitTracker:
    def __init__(self):
        # Sliding window management - LIST-BASED TRACKING
        self.trailing_stop: List[int] = [-4, -3, -2, -1]  # Initial stops
        self.trailing_buy: List[int] = []  # Initially empty

    def get_window_state(self) -> dict:
        """Get current window state for monitoring"""
        return {
            'current_unit': self.current_unit,
            'phase': self.get_phase(),
            'trailing_stop': self.trailing_stop.copy(),
            'trailing_buy': self.trailing_buy.copy(),
            'total_orders': len(self.trailing_stop) + len(self.trailing_buy)
        }
```

## Complete Scenarios

### Scenario 1: Bull Run (Pure ADVANCE)
1. Entry at $100 (unit 0)
2. Initial stops at units [-4, -3, -2, -1] → prices [96, 97, 98, 99]
3. Price rises to $101 (unit 1)
   - Cancel stop at unit -4 ($96)
   - Place new stop at unit 0 ($100)
   - Stops now at [-3, -2, -1, 0] → [97, 98, 99, 100]
4. Price rises to $102 (unit 2)
   - Cancel stop at unit -3 ($97)
   - Place new stop at unit 1 ($101)
   - Stops now at [-2, -1, 0, 1] → [98, 99, 100, 101]
5. Continue pattern as price rises...

### Scenario 2: Peak and Decline
1. Price peaks at $108 (unit 8)
   - Stops at [4, 5, 6, 7] → [104, 105, 106, 107]
2. Price drops to $107 (unit 7)
   - Phase transition to DECLINE
   - Cancel ALL stops
   - Place buys at [8, 9, 10, 11] → [108, 109, 110, 111]
3. Price drops to $106 (unit 6)
   - Cancel buy at unit 11 ($111)
   - Place new buy at unit 7 ($107)
   - Buys now at [7, 8, 9, 10] → [107, 108, 109, 110]
4. Continue sliding buys down...

### Scenario 3: Recovery Phase
1. Price bottoms at $102 (unit 2), buys at [3, 4, 5, 6]
2. Price rises to $103 (unit 3), triggers buy
   - Buy order at unit 3 fills
   - Remove from trailing_buy list
   - Now have 3 buys: [4, 5, 6]
3. Price rises to $104 (unit 4), triggers another buy
   - Buy order at unit 4 fills
   - Now have 2 buys: [5, 6]
   - Place new stop at unit 3 ($103)
   - Mixed state: 1 stop, 2 buys
4. Continue until fully recovered to ADVANCE phase

### Scenario 4: Retracement During Advance
1. Price at $106 (unit 6), stops at [2, 3, 4, 5]
2. Price drops to $105 (unit 5), triggers stop
   - Stop at unit 5 sells position fragment
   - Remove from trailing_stop list
   - Now have 3 stops: [2, 3, 4]
3. Price drops to $104 (unit 4), triggers another stop
   - Stop at unit 4 sells fragment
   - Now have 2 stops: [2, 3]
   - Place new buy at unit 5 ($105)
   - Mixed state: 2 stops, 1 buy
4. If price recovers, buys trigger and return to ADVANCE

## Key Implementation Principles

1. **List-Based Tracking**: Orders managed through `trailing_stop` and `trailing_buy` lists
2. **Sliding Window**: Maintains up to 4 orders on each side (stops below, buys above)
3. **Adaptive Order Types**: Stop buys become limit orders when price drops below trigger
4. **Real-Time WebSocket**: Price updates trigger unit changes via WebSocket callbacks
5. **Asynchronous Execution**: Orders placed using `asyncio.create_task()` for non-blocking operation
6. **PnL Reinvestment**: Realized profits tracked and reinvested in recovery phase

## Architecture Highlights

### Order Management Flow:
1. **Price Update** → WebSocket callback (`_handle_price_update`)
2. **Unit Detection** → UnitTracker calculates boundary crossing
3. **Order Placement** → Async task spawned for order operations
4. **List Updates** → Trailing lists maintained at max 4 entries
5. **Fill Handling** → WebSocket fills trigger replacement orders

### Smart Order Placement:
- **Stop Loss**: Always uses stop orders (triggered when price drops)
- **Stop Buy**: Uses stop orders above market, limit orders below market
- **Duplicate Prevention**: Checks for existing orders before placement
- **Price Validation**: Ensures proper spacing between unit prices

## Testing Scenarios

### Test 1: Rapid Advance
- Start at unit 0
- Move quickly to unit 10
- Verify stops slide smoothly from [-4,-3,-2,-1] to [6,7,8,9]

### Test 2: Deep Decline
- Peak at unit 8
- Drop to unit -2
- Verify transition to buys and sliding down properly

### Test 3: Volatile Sideways
- Oscillate between units 3-5
- Verify mixed states handle correctly
- Check PnL accumulation in recovery phases

### Test 4: Unit 0 Crossing
- Move from unit 1 to unit -1
- Verify unit 0 orders placed and maintained correctly
- Confirm no special treatment of zero boundary