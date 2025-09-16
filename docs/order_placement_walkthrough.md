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

### 1. Initial Entry (backend/src/main.py: initialize_position)
```python
async def initialize_position():
    # Place initial market buy order
    await exchange_client.place_market_order(
        symbol=symbol,
        side="buy",
        size=position_size
    )

    # Set up initial trailing stops at units -4, -3, -2, -1
    for unit in [-4, -3, -2, -1]:
        await _place_stop_order(unit, OrderType.STOP_LOSS_SELL)
```

**State After Entry:**
- Current unit: 0
- Trailing stops: [-4, -3, -2, -1]
- Trailing buys: []
- Phase: ADVANCE

### 2. Price Movement Detection (backend/src/main.py: main_loop)
```python
async def main_loop():
    while running:
        # Get current price
        price = await exchange_client.get_mark_price()

        # Check for unit boundary crossing
        unit_change = unit_tracker.calculate_unit_change(price)

        if unit_change:
            await _handle_unit_change(unit_change)
```

### 3. Unit Change Handling (backend/src/main.py: _handle_unit_change)

#### Scenario A: Price Moving UP (ADVANCE Phase)
**Initial State:** Price at unit 0, moving to unit 1

```python
async def _handle_unit_change(event: UnitChangeEvent):
    if event.direction == 'up':
        # 1. Cancel the furthest stop (unit -4)
        old_stop = current_unit - 4
        await exchange_client.cancel_order(old_stop)
        unit_tracker.remove_trailing_stop(old_stop)

        # 2. Place new stop at current unit
        new_stop = current_unit
        asyncio.create_task(_place_stop_order(new_stop, STOP_LOSS_SELL))
        unit_tracker.add_trailing_stop(new_stop)
```

**Result:** Trailing stops slide up to [-3, -2, -1, 0]

#### Scenario B: Price Moving DOWN (DECLINE Phase)
**Initial State:** Price peaked at unit 8, now moving to unit 7

```python
async def _handle_unit_change(event: UnitChangeEvent):
    if event.direction == 'down':
        # Phase transition: stops become buys
        if len(trailing_buy) == 0:  # First decline
            # Cancel all stops, place buys above
            for unit in trailing_stop:
                await exchange_client.cancel_order(unit)
            trailing_stop.clear()

            # Place buys at [8, 9, 10, 11]
            for i in range(4):
                buy_unit = current_unit + i + 1
                asyncio.create_task(_place_stop_order(buy_unit, STOP_BUY))
                unit_tracker.add_trailing_buy(buy_unit)
```

**Result:** Trailing buys at [8, 9, 10, 11], no stops

### 4. Sliding Window Management

#### ADVANCE: Sliding Stops UP
```python
async def _slide_window_up():
    # Cancel orders too far behind (>4 units)
    for unit in list(trailing_stop):
        if unit < current_unit - 4:
            await exchange_client.cancel_order(unit)
            unit_tracker.remove_trailing_stop(unit)

    # Place new stops up to current unit
    for i in range(4):
        target_unit = current_unit - i
        if target_unit not in trailing_stop:
            asyncio.create_task(_place_stop_order(target_unit, STOP_LOSS_SELL))
            unit_tracker.add_trailing_stop(target_unit)
```

#### DECLINE: Sliding Buys DOWN
```python
async def _slide_window_down():
    # Cancel orders too far above (>4 units)
    for unit in list(trailing_buy):
        if unit > current_unit + 4:
            await exchange_client.cancel_order(unit)
            unit_tracker.remove_trailing_buy(unit)

    # Place new buys above current unit
    for i in range(1, 5):
        target_unit = current_unit + i
        if target_unit not in trailing_buy:
            asyncio.create_task(_place_stop_order(target_unit, STOP_BUY))
            unit_tracker.add_trailing_buy(target_unit)
```

### 5. Order Execution Handling (backend/src/main.py: handle_fill)

#### Stop Loss Execution
```python
async def handle_fill(fill_data):
    if order.order_type == OrderType.STOP_LOSS_SELL:
        # Remove from tracking
        unit_tracker.remove_trailing_stop(unit)

        # In DECLINE phase, this creates space for new buy
        if phase == "decline":
            # Window will adjust on next unit change
            pass
```

#### Stop Buy Execution
```python
async def handle_fill(fill_data):
    if order.order_type == OrderType.STOP_BUY:
        # Remove from tracking
        unit_tracker.remove_trailing_buy(unit)

        # Track PnL for reinvestment
        unit_tracker.track_realized_pnl(sell_price, buy_price, size)

        # In RECOVERY phase, this creates space for new stop
        if phase == "recovery":
            # Window will adjust on next unit change
            pass
```

### 6. Order Validation (backend/src/main.py: _validate_order_placement)

Continuous validation ensures orders stay on correct side of price:

```python
async def _validate_order_placement():
    current_unit = unit_tracker.current_unit

    # Cancel invalid stop orders (should be BELOW price)
    for unit in list(trailing_stop):
        if unit > current_unit:
            logger.error(f"INVALID: Stop at {unit} is ABOVE price")
            await exchange_client.cancel_order(unit)
            unit_tracker.remove_trailing_stop(unit)

    # Cancel invalid buy orders (should be ABOVE price)
    for unit in list(trailing_buy):
        if unit < current_unit:  # Note: < not <= to allow orders AT current unit
            logger.error(f"INVALID: Buy at {unit} is BELOW price")
            await exchange_client.cancel_order(unit)
            unit_tracker.remove_trailing_buy(unit)
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

## Key Principles

1. **Immediate Placement**: Orders placed instantly on unit crossing via `asyncio.create_task()`
2. **Sliding Window**: Always maintain 4 trailing orders (stops OR buys)
3. **Phase-Based Logic**: Order types determined by current phase
4. **Continuous Validation**: Invalid orders cancelled in main loop
5. **Unit Agnostic**: Unit 0 treated same as any other unit
6. **PnL Tracking**: Realized profits tracked for reinvestment in recovery

## Error Prevention

### Common Issues Fixed:
1. **Orders on wrong side**: Validation ensures stops below, buys above
2. **Window not sliding**: Proper cancellation of distant orders
3. **Unit 0 special treatment**: Fixed validation to allow orders AT current unit
4. **Undefined variables**: Removed legacy code references
5. **Sluggish placement**: Made asynchronous with create_task()

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