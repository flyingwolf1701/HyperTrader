# Advanced Hedging Strategy v9.2.6 - Sliding Window Order Management

## Core Philosophy

This is a bull market thesis strategy engineered to capitalize on price movements in both directions while maintaining a long-term upward bias. The system leverages automated execution across **two separate wallets** on the Hyperliquid platform to overcome position netting constraints and achieve true portfolio diversification. The strategy systematically takes profits during price retracements and compounds returns during recoveries through **sliding window order management**.

The strategy is centered around a dynamic sliding window system that continuously maintains 4 active limit orders trailing the current price position, allowing for seamless execution in both trending and ranging markets.

## Dual-Wallet Architecture

### Position Netting Challenge

**The Fundamental Constraint**: On Hyperliquid (and most exchanges), you cannot hold both long and short positions simultaneously in the same asset on a single wallet. When attempting to "open" a short position while holding a long position, the positions automatically net against each other, reducing the long position instead of creating separate hedging positions.

**The Solution**: **Dual-Wallet Architecture** - Split execution across two separate wallets with distinct strategic roles to achieve true portfolio diversification. **Note**: Each wallet operates independently with its own sliding window order management.

### Wallet Allocation and Roles

**Long Wallet (50% of total allocation)**:
- **Purpose**: Execute fragment-based scaling strategy with gradual position management
- **Initial Allocation**: 50% of desired total position size
- **Strategy**: Maintains continuous 4-order sliding window that trails price movement
- **Fragment Approach**: 25% position fragments (ETH for sells, USD for buys)
- **Risk Profile**: Conservative scaling through gradual position transitions

**Hedge Wallet (50% of total allocation)**:
- **Purpose**: Provide aggressive counter-movement positioning through short exposure
- **Initial Allocation**: 50% of desired total position size
- **Strategy**: Maintains continuous 4-order sliding window for short/cover positions
- **Key Difference**: Transitions from long → cash → short → cash → long (full rotation)
- **Risk Profile**: Maximum exposure to directional moves through complete position changes


## Long Wallet Sliding Window Order Management System

### Core Principle: Continuous 4-Order Trailing Window

The strategy maintains **4 active limit orders** at all times, positioned to trail the current price by 1 unit. This sliding window automatically adjusts as price moves, ensuring continuous market coverage without manual intervention.

**Initial Setup**: Place 4 sell limit orders at [current-4, current-3, current-2, current-1] using 25% position fragments

### Phase-Based Order Management

**ADVANCE Phase**:
- **Trigger**: Price trending upward from entry or reset point
- **State**: 100% long position, 4 sell orders active
- **Actions**: 
    - As current unit increases: Add sell at (current - 1), cancel sell at (current - 5)
    - Maintain 4 sell orders trailing 1 unit behind current price
- **Transition**: Enters RETRACEMENT when first sell order executes

**RETRACEMENT Phase**:
- **Trigger**: First sell order executes from ADVANCE phase
- **State**: Mixed position (ETH + cash), mix of buy/sell orders
- **Actions**:
    - Sell execution: Replace with buy order at current+1
    - Buy execution: Replace with sell order at current-1
    - Maintain total of 4 orders across buy/sell lists
- **Transitions**: 
    - To DECLINE: All 4 sells executed (100% cash)
    - To RESET: All 4 buys executed (100% long)

**DECLINE Phase**:
- **Trigger**: All sell orders executed, position 100% cash
- **State**: No ETH position, 4 buy orders active
- **Actions**:
    - As current unit decreases: Add buy at (current + 1), cancel buy at (current + 5)
    - Maintain 4 buy orders positioned 1 unit ahead of current price
- **Transition**: Enters RECOVER when first buy order executes

**RECOVER Phase**:
- **Trigger**: First buy order executes from DECLINE phase
- **State**: Mixed position (ETH + cash), mix of buy/sell orders
- **Actions**:
    - Sell execution: Replace with buy order at current+1
    - Buy execution: Replace with sell order at current-1
    - Maintain total of 4 orders across buy/sell lists
- **Transitions**:
    - To RESET: All 4 buys executed (100% long)
    - To DECLINE: All 4 sells executed (100% cash)

**RESET Mechanism**:
- **Trigger**: Portfolio returns to 100% long from RETRACEMENT or RECOVER
- **Actions**:
    - Reset unit counters to 0
    - Update allocation values based on new position value (capturing compound growth)
    - Reinitialize 4 sell orders at [current-4, current-3, current-2, current-1]
- **Result**: Returns to ADVANCE phase with compounded position

## Fragment-Based Position Management

### Core Fragment Principle

**Fragment Definition**: Each fragment represents 25% of the total position
- **Sell Fragments**: Fixed ETH amounts (locked at initialization)
- **Buy Fragments**: Fixed USD amounts (25% of initial allocation)
- **Total Fragments**: 4 fragments = complete position

**Why ETH Sells / USD Buys**:
- Selling fixed ETH amounts ensures consistent position reduction regardless of price
- Buying fixed USD amounts ensures consistent capital deployment
- This asymmetry captures value: sell high ETH amounts, buy back more ETH at lower prices

## Sliding Window Example

### Typical Market Cycle

**Starting Position (Unit 0)**:
- Orders: 4 sells at [-4, -3, -2, -1]
- Position: 100% long

**Price Advances to Unit +7**:
- Window slides up: sells now at [+3, +4, +5, +6]
- Position: Still 100% long

**Retracement to Unit +4**:
- Sells at +6, +5 executed → replaced with buys at +5, +4 respectively
- Orders: 2 sells [+3, +4], 2 buys [+4, +5]
- Position: 50% ETH, 50% cash

**Further Drop to Unit +2**:
- All sells executed → replaced with buys one unit ahead
- Orders: 4 buys at [+1, +2, +3, +4]
- Position: 100% cash (DECLINE phase)

**Recovery to Unit +5**:
- Buys at +1, +2, +3 executed → replaced with sells one unit behind
- Orders: 1 buy [+4], 3 sells [+2, +3, +4]
- Position: 75% ETH, 25% cash

### Key Order Management Rules

1. **Always maintain exactly 4 active orders** (combination of buy/sell)
2. **Order Replacement Logic**:
   - Sell executes → Place buy at current+1
   - Buy executes → Place sell at current-1
3. **Fragment amounts remain fixed** throughout entire cycle
4. **Window slides automatically** in trending phases (ADVANCE/DECLINE)

## Implementation Notes

### Phase Detection Logic

The system automatically detects the current phase based on:
- **Order composition**: All sells = ADVANCE, All buys = DECLINE, Mix = RETRACEMENT/RECOVER
- **Position state**: 100% ETH = ADVANCE, 100% Cash = DECLINE, Mixed = transitional phases
- **Recent executions**: Pattern of completed orders determines phase transitions

### Compound Growth Mechanism

The strategy achieves compound growth through:
1. **Selling high**: Fixed ETH amounts sold as price rises
2. **Buying low**: Fixed USD amounts buy more ETH at lower prices
3. **RESET capture**: New cycle starts with larger base position
4. **Continuous compounding**: Each cycle builds on previous gains

## Hedge Wallet Strategy: Short-Focused Sliding Windows

### Core Principle: Short-Side 4-Order Trailing Window

The hedge wallet transitions through distinct position states: Long → Cash → Short → Cash → Long. It maintains **4 active orders** for shorts/covers, positioned to trail the current price by 1 unit.

**Initial Setup**: 
- Start with 100% long position
- Place 1 sell order at (current-1) to exit long completely
- Prepare 4 short orders at [current-1, current-2, current-3, current-4]

### Phase-Based Order Management

**ADVANCE Phase (Hedge Wallet)**:
- **Trigger**: Price trending upward from entry or reset point
- **State**: Initially long, then cash after sell executes, short orders active
- **Actions**:
    - Long position exits when sell order at (current-1) executes
    - As current unit increases: Add short at (current-1), cancel short at (current-5)
    - Maintain 4 short orders trailing 1 unit behind current price
- **Transition**: Enters RETRACEMENT when first short order executes

**RETRACEMENT Phase (Hedge Wallet)**:
- **Trigger**: First short order executes from ADVANCE phase
- **State**: Mixed short position, mix of short/cover orders
- **Actions**:
    - Short execution: Replace with cover order at current+1
    - Cover execution: Replace with short order at current-1
    - Maintain total of 4 orders across short/cover lists
- **Transitions**:
    - To DECLINE: All 4 shorts executed (maximum short exposure)
    - To RESET: All 4 covers executed (100% cash, ready for long entry)

**DECLINE Phase (Hedge Wallet)**:
- **Trigger**: All short orders executed, maximum short exposure
- **State**: 100% short position, 4 cover orders active
- **Actions**:
    - As current unit decreases: Add cover at (current+1), cancel cover at (current+5)
    - Maintain 4 cover orders positioned 1 unit ahead of current price
- **Transition**: Enters RECOVER when first cover order executes

**RECOVER Phase (Hedge Wallet)**:
- **Trigger**: First cover order executes from DECLINE phase
- **State**: Mixed short position, mix of short/cover orders
- **Actions**:
    - Cover execution: Replace with short order at current-1
    - Short execution: Replace with cover order at current+1
    - Maintain total of 4 orders across short/cover lists
- **Transitions**:
    - To RESET: All 4 covers executed (100% cash)
    - To DECLINE: All 4 shorts executed (back to maximum short)

**RESET Mechanism (Hedge Wallet)**:
- **Trigger**: All cover orders executed, position 100% cash
- **Actions**:
    - Place single large long entry order using all cash (including short profits)
    - Reset unit counters to 0
    - Once long filled, place new sell order at (current-1)
    - Prepare new short orders
- **Result**: Returns to ADVANCE phase with compounded long position

### Fragment-Based Position Management (Hedge Wallet)

**Core Fragment Principle**:
- **Initial Long Exit**: 100% of position sold in single order
- **Short Fragments**: Fixed USD amounts (25% of initial allocation each)
- **Cover Fragments**: Fixed ETH amounts (25% of short position each)
- **Long Re-entry**: Single order using all cash (original + short profits)

**Why USD Shorts / ETH Covers**:
- Shorting fixed USD amounts ensures consistent exposure
- Covering fixed ETH amounts ensures consistent position reduction
- This asymmetry captures value: short at high prices, cover more ETH at lower prices

### Sliding Window Example (Hedge Wallet)

**Starting Position (Unit 0)**:
- Position: 100% long
- Orders: 1 sell at -1, 4 shorts ready

**Price Advances to Unit +7**:
- Sell executed at +6 → Position now cash
- Short window slides: shorts at [+3, +4, +5, +6]

**Retracement to Unit +4**:
- Shorts at +6, +5 executed → replaced with covers at +5, +4
- Orders: 2 shorts [+3, +4], 2 covers [+4, +5]
- Position: 50% short exposure

**Further Drop to Unit +2**:
- All shorts executed → replaced with covers one unit ahead
- Orders: 4 covers at [+1, +2, +3, +4]
- Position: Maximum short exposure (DECLINE phase)

**Recovery to Unit +5**:
- Covers at +1, +2, +3 executed → replaced with shorts one unit behind
- Orders: 1 cover [+4], 3 shorts [+2, +3, +4]
- Position: 25% short remaining

**Full Recovery to Unit +7**:
- All covers executed → 100% cash with profits
- Place single long entry with all capital
- RESET triggered once long fills

### Key Order Management Rules (Hedge Wallet)

1. **Maintain 4 active orders** for short/cover positions
2. **Order Replacement Logic**:
   - Short executes → Place cover at current+1
   - Cover executes → Place short at current-1
3. **Position Transitions**:
   - Long → Cash (single sell order)
   - Cash → Short (via 4 fragment orders)
   - Short → Cash (via 4 cover orders)
   - Cash → Long (single large entry)
4. **Window slides automatically** in trending phases

### Implementation Notes (Hedge Wallet)

**Phase Detection Logic**:
- **Position state**: Long, Cash, Short, or Mixed
- **Order composition**: Determines current phase
- **Recent executions**: Triggers phase transitions

**Compound Growth Through Rotation**:
1. **Exit long high**: Sell entire position as price rises
2. **Short the retracement**: Enter shorts at elevated prices
3. **Cover shorts low**: Exit shorts as price declines
4. **Re-enter long with profits**: Single entry with original capital + short profits
5. **RESET captures gains**: New cycle with larger base position

## Risk Management Through Sliding Windows

### Advantages of Sliding Window Approach

**Continuous Market Coverage**:
- Always have orders positioned for next 4 price movements
- No gaps in coverage during volatile periods
- Automatic adjustment to changing market conditions

**Execution Independence**:
- Orders execute based on price action, not manual decisions
- No coordination required between individual orders
- Natural profit-taking during retracements

**Loss Minimization**:
- Small losses acceptable (buying back higher, selling again lower)
- Prevents large losses through continuous scaling
- Maintains directional bias while capturing volatility

### Order Execution Flow

**Automatic Execution**:
1. **Limit Hit**: Exchange executes order automatically at predetermined price
2. **System Notification**: Bot receives fill notification via WebSocket
3. **Position Update**: Update internal position tracking
4. **Order Replacement**: Place opposite order type at executed level
5. **Window Adjustment**: Maintain 4-order sliding window

**No Real-Time Decisions**: All trading decisions are predetermined through the sliding window structure.

## Implementation Architecture

### Technical Components

**Position Map Integration**:
- `PositionState`: Static configuration (entry price, unit size, fragments)
- `PositionConfig`: Dynamic per-unit state (order IDs, execution status)
- Fragment calculations locked at initialization

**Order State Tracking**:
- Active order IDs mapped to unit levels
- Execution status per order (pending, filled, cancelled)
- Order type tracking (sell vs buy) per unit level

**WebSocket Integration**:
- Real-time order fill notifications
- Price movement detection for window adjustments
- Connection resilience for continuous operation

### Sliding Window Management Algorithm

```python
def manage_dual_sliding_windows(current_unit, direction):
    if direction == "up":
        # Slide both windows up
        if sell_window:
            add_sell_order(current_unit - 1)
            cancel_sell_order(current_unit - 5)
        if buy_window:
            add_buy_order(current_unit + 4)
            cancel_buy_order(current_unit)
            
    elif direction == "down":
        # Slide both windows down
        if sell_window:
            cancel_sell_order(current_unit + 4)
            # Don't add new sells below current
        if buy_window:
            add_buy_order(current_unit + 1)
            cancel_buy_order(current_unit + 5)
        
def handle_order_execution(executed_unit, order_type):
    if order_type == "sell":
        # Remove from sell window, add to buy window
        remove_from_sell_window(executed_unit)
        add_to_buy_window(executed_unit)
        # Update position: decrease ETH, increase cash
        
    elif order_type == "buy":
        # Remove from buy window, add to sell window
        remove_from_buy_window(executed_unit)
        add_to_sell_window(executed_unit)
        # Update position: increase ETH, decrease cash
```

## Expected Performance Benefits

**Enhanced Execution**:
- Consistent fragment-based scaling regardless of market volatility
- Automatic profit-taking during retracements
- Natural position rebuilding during recoveries

**Reduced Complexity**:
- Elimination of complex phase tracking
- Simplified order management through sliding windows
- Independent order execution reduces coordination overhead

**Improved Resilience**:
- Continuous market coverage through all market conditions
- Automatic adjustment to trending vs ranging markets
- Natural loss minimization through fragment scaling

## Strategy Evolution: v8.2.0 → v9.0.0

**Key Changes**:
- Complex phase-based logic → Simplified sliding window management
- Peak/valley tracking → Continuous window adjustment
- Manual order coordination → Automatic window maintenance
- Phase-dependent strategies → Universal sliding window approach

**Maintained Elements**:
- Dual wallet architecture for true diversification
- Fragment-based position management
- Limit order execution philosophy
- Bull market thesis and directional bias
- Reset mechanism for compound growth

**Implementation Benefits**:
- Clearer order management logic
- Reduced coordination complexity
- More predictable execution patterns
- Simplified state management

The Advanced Hedging Strategy v9.0.0 represents a significant simplification of the order management system while maintaining the sophisticated market timing and profit compounding capabilities through the elegant sliding window approach.