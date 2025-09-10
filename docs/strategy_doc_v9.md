# Advanced Hedging Strategy v9.4.12 - Sliding Window Order Management

## Core Philosophy

This is a bull market thesis strategy engineered to capitalize on price movements in both directions while maintaining a long-term upward bias. The system leverages automated execution across **two separate wallets** on the Hyperliquid platform to overcome position netting constraints and achieve true portfolio diversification. The strategy systematically takes profits during price retracements and compounds returns during recoveries through **sliding window order management**.

The strategy is centered around a dynamic sliding window system that continuously maintains 4 active orders (stop-loss or limit orders depending on direction) trailing the current price position, allowing for seamless execution in both trending and ranging markets.

## Dual-Wallet Architecture

### Position Netting Challenge

**The Fundamental Constraint**: On Hyperliquid (and most exchanges), you cannot hold both long and short positions simultaneously in the same asset on a single wallet. When attempting to "open" a short position while holding a long position, the positions automatically net against each other, reducing the long position instead of creating separate hedging positions.

**The Solution**: **Dual-Wallet Architecture** - Split execution across two separate wallets with distinct strategic roles to achieve true portfolio diversification. **Note**: Each wallet operates independently with its own sliding window order management.

### Wallet Allocation and Roles

**Long Wallet (50% of total allocation)**:
- **Purpose**: Execute fragment-based scaling strategy with gradual position management
- **Initial Allocation**: 50% of desired total position size
- **Strategy**: Maintains two sliding windows and 4 active orders
    - `stop_loss_orders`: initially contains 4 trailing stop losses based on the price of the current unit
    - `limit_buy_orders`: initially empty
- **Fragment Approach**: 25% position fragments (Stop losses are measured in the amount of COIN you wish to sell on retracement)
- **Risk Profile**: Conservative scaling through gradual position transitions should have portfolio in cash during significant down turns preserving capital.

**Hedge Wallet (50% of total allocation)**:
- **Purpose**: Provide aggressive counter-movement positioning through short exposure
- **Initial Allocation**: 50% of desired total position size
- **Strategy**: Maintains two sliding windows and 4 or 5 active orders
    - `stop_loss_full_long`: initially placed at current-1 to exit long completely trails current_unit
    - `enter_short_orders`: intitially 4 limit short orders are placed starting at current-1
    - `stop_loss_orders_hedge`: initially empty, But when a short order executes a stop loss is placed at current+1
    - `market_buy_full_long_orders`: initially empty. Tracks `stop_loss_orders_hedge` after this window is empty a market order         
        is placed to enter full long position
- **Fragment Approach**: 25% position fragments
- **Key Difference**: Transitions from long → cash → short → cash → long (full rotation)
- **Risk Profile**: Maximum exposure to directional moves through complete position changes

## User Initialization and Setup

### Strategy Selection

Users can deploy capital to either or both strategies independently:
- **Long Wallet Only**: Conservative approach with gradual scaling
- **Hedge Wallet Only**: Aggressive approach with short exposure
- **Both Wallets**: Full hedging strategy with maximum diversification

### Required User Inputs

**Per-Strategy Configuration**:
- **Long Wallet Allocation**: USD amount for Long Wallet strategy (0 if not using)
- **Hedge Wallet Allocation**: USD amount for Hedge Wallet strategy (0 if not using)
- **Leverage Setting**: Leverage multiplier per wallet (1x-20x recommended)
- **Asset Selection**: The specific coin/token to trade (e.g., ETH, BTC)

**Unit Size Definition**:
- **Price Unit Size**: The dollar amount that constitutes one "unit" of price movement
  - Example: $100 unit size means each unit represents a $100 price change
  - Alternative: Percentage-based units (e.g., 1% of current price)
  - Alternative: ATR-based units (e.g., 0.5x Average True Range)
- **Unit Rounding**: Round to nearest exchange-supported price increment

**Fragment Calculation**:
- **Long Wallet Fragments** (if enabled): 
  - Each fragment = 25% of leveraged position
  - Stop-loss sells: (Total ETH Position × 0.25) per fragment
  - Limit buys: (Total USD Allocation × 0.25) per fragment
- **Hedge Wallet Fragments** (if enabled):
  - Exit long: 100% of position in single order
  - Short entries: (Total USD Allocation × 0.25) per fragment
  - Short exits: (Total Short Position in ETH × 0.25) per fragment

### Initial Order Placement Process

**Step 1: Establish Starting Positions**
1. Each enabled wallet begins with 100% long position at current market price
2. Record entry price as Unit 0 reference point
3. Calculate fragment sizes based on leveraged positions for each enabled wallet

**Step 2: Long Wallet Initial Orders** (if Long Wallet enabled)
1. Calculate unit levels: [current-4, current-3, current-2, current-1]
2. Place 4 stop-loss sell orders at these levels
3. Each order size = 25% of ETH position
4. Set `limit_buy_orders` list as empty

**Step 3: Hedge Wallet Initial Orders** (if Hedge Wallet enabled)
1. Place `stop_loss_full_long` at (current-1) for 100% of position
2. Prepare `enter_short_orders` at levels BELOW current price:
   - Use stop-entry orders at [current-1, current-2, current-3, current-4]
   - Each order size = 25% of USD allocation
3. Set `stop_loss_orders_hedge` list as empty
4. Set `market_buy_full_long_orders` as empty

**Step 4: Verify and Activate**
1. Confirm all orders are accepted by exchange
2. Verify leverage settings are applied
3. Enable WebSocket monitoring for price updates
4. Begin sliding window management for enabled strategies

## Long Wallet Sliding Window Order Management System

### Core Principle: Continuous 4-Order Trailing Window

The strategy maintains **4 active orders** at all times (stop-loss sells OR limit buys), positioned to trail the current price by 1 unit. This sliding window automatically adjusts as price moves, ensuring continuous market coverage without manual intervention.

**Initial Setup**: Place 4 stop-loss sell orders at [current-4, current-3, current-2, current-1] using 25% position fragments

### Phase-Based Order Management

**ADVANCE Phase**:
- **Trigger**: Price trending upward from entry or reset point
- **State**: 100% long position, 4 stop-loss sell orders active
- **Actions**: 
    - As current unit increases: Add stop-loss at (current - 1), cancel stop-loss at (current - 5)
    - Maintain 4 stop-loss orders trailing 1 unit behind current price
- **Transition**: Enters RETRACEMENT when first stop-loss triggers

**RETRACEMENT Phase**:
- **Trigger**: First stop-loss triggers from ADVANCE phase
- **State**: Mixed position (ETH + cash), mix of limit buy/stop-loss orders
- **Actions**:
    - Stop-loss triggers: Replace with limit buy order at current+1
    - Limit buy fills: Replace with stop-loss order at current-1
    - Maintain total of 4 orders across both order types
- **Transitions**: 
    - To DECLINE: All 4 stop-losses triggered (100% cash)
    - To RESET: All 4 limit buys filled (100% long)

**DECLINE Phase**:
- **Trigger**: All stop-loss orders triggered, position 100% cash
- **State**: No ETH position, 4 limit buy orders active
- **Actions**:
    - As current unit decreases: Add limit buy at (current + 1), cancel limit buy at (current + 5)
    - Maintain 4 limit buy orders positioned 1 unit ahead of current price
- **Transition**: Enters RECOVER when first limit buy fills

**RECOVER Phase**:
- **Trigger**: First limit buy fills from DECLINE phase
- **State**: Mixed position (ETH + cash), mix of limit buy/stop-loss orders
- **Actions**:
    - Stop-loss triggers: Replace with limit buy order at current+1
    - Limit buy fills: Replace with stop-loss order at current-1
    - Maintain total of 4 orders across both order types
- **Transitions**:
    - To RESET: All 4 limit buys filled (100% long)
    - To DECLINE: All 4 stop-losses triggered (100% cash)

**RESET Mechanism**:
- **Trigger**: Portfolio returns to 100% long from RETRACEMENT or RECOVER
- **Actions**:
    - Reset unit counters to 0
    - Update allocation values based on new position value (capturing compound growth)
    - Reinitialize 4 stop-loss orders at [current-4, current-3, current-2, current-1]
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
- Orders: 4 stop-losses at [-4, -3, -2, -1]
- Position: 100% long

**Price Advances to Unit +7**:
- Window slides up: stop-losses now at [+3, +4, +5, +6]
- Position: Still 100% long

**Retracement to Unit +4**:
- Stop-losses at +6, +5 triggered → replaced with limit buys at +5, +4 respectively
- Orders: 2 stop-losses [+3, +4], 2 limit buys [+4, +5]
- Position: 50% ETH, 50% cash

**Further Drop to Unit +2**:
- All stop-losses triggered → replaced with limit buys one unit ahead
- Orders: 4 limit buys at [+1, +2, +3, +4]
- Position: 100% cash (DECLINE phase)

**Recovery to Unit +5**:
- Limit buys at +1, +2, +3 filled → replaced with stop-losses one unit behind
- Orders: 1 limit buy [+4], 3 stop-losses [+2, +3, +4]
- Position: 75% ETH, 25% cash

### Key Order Management Rules

1. **Always maintain exactly 4 active orders** (combination of stop-loss/limit buy)
2. **Order Replacement Logic**:
   - Stop-loss triggers → Place limit buy at current+1
   - Limit buy fills → Place stop-loss at current-1
3. **Fragment amounts remain fixed** throughout entire cycle
4. **Window slides automatically** in trending phases (ADVANCE/DECLINE)

## Implementation Notes

### Phase Detection Logic

The system automatically detects the current phase based on:
- **Order composition**: All stop-losses = ADVANCE, All limit buys = DECLINE, Mix = RETRACEMENT/RECOVER
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

The hedge wallet transitions through distinct position states: Long → Cash → Short → Cash → Long. It maintains **4-5 active orders** across different order types.

**Initial Setup**: 
- Start with 100% long position
- Place 1 stop-loss at (current-1) to exit long completely (`stop_loss_full_long`)
- Place 4 stop-entry short orders at [current-1, current-2, current-3, current-4] (`enter_short_orders`)
  - These are stop orders that trigger SHORT positions when price falls TO or BELOW the trigger level
- `stop_loss_orders_hedge`: Initially empty (populated as shorts execute)
- `market_buy_full_long_orders`: Initially empty (used for re-entry)

### Phase-Based Order Management

**ADVANCE Phase (Hedge Wallet)**:
- **Trigger**: Price trending upward from entry or reset point
- **State**: Initially long with stop-loss active, stop-entry short orders ready below price
- **Actions**:
    - `stop_loss_full_long` trails at (current-1) until triggered
    - Once stop-loss triggers: Position becomes 100% cash
    - Stop-entry shorts wait at [current-1, current-2, current-3, current-4]
    - As current unit increases: Add stop-entry short at (current-1), cancel oldest at (current-5)
    - Maintain 4 stop-entry short orders trailing 1 unit behind current price
- **Transition**: Enters RETRACEMENT when price falls and first stop-entry short triggers

**RETRACEMENT Phase (Hedge Wallet)**:
- **Trigger**: First stop-entry short order triggers from ADVANCE phase
- **State**: Mixed short position, combination of stop-entry shorts and stop-losses
- **Actions**:
    - Stop-entry short triggers: Add to `stop_loss_orders_hedge` at current+1
    - Stop-loss triggers: Remove from `stop_loss_orders_hedge`, add stop-entry short at current-1
    - Maintain 4 orders total across `enter_short_orders` and `stop_loss_orders_hedge`
- **Transitions**:
    - To DECLINE: All 4 stop-entry shorts triggered (maximum short exposure)
    - To RESET: All stop-losses triggered (100% cash, ready for long entry)

**DECLINE Phase (Hedge Wallet)**:
- **Trigger**: All stop-entry short orders triggered, maximum short exposure
- **State**: 100% short position, 4 stop-loss orders active in `stop_loss_orders_hedge`
- **Actions**:
    - As current unit decreases: Add stop-loss at (current+1), cancel stop-loss at (current+5)
    - Maintain 4 stop-loss orders positioned 1 unit ahead of current price
- **Transition**: Enters RECOVER when first stop-loss triggers

**RECOVER Phase (Hedge Wallet)**:
- **Trigger**: First stop-loss triggers from DECLINE phase
- **State**: Mixed short position, combination of stop-losses and stop-entry shorts
- **Actions**:
    - Stop-loss triggers: Remove from `stop_loss_orders_hedge`, add stop-entry short at current-1
    - Stop-entry short triggers: Add to `stop_loss_orders_hedge` at current+1
    - Maintain 4 orders total across both order types
- **Transitions**:
    - To RESET: All stop-losses triggered (100% cash)
    - To DECLINE: All stop-entry shorts triggered (back to maximum short)

**RESET Mechanism (Hedge Wallet)**:
- **Trigger**: All stop-losses triggered, position 100% cash
- **Actions**:
    - Place market buy order using all cash (including short profits) via `market_buy_full_long_orders`
    - Reset unit counters to 0
    - Once long filled, place new `stop_loss_full_long` at (current-1)
    - Reinitialize `enter_short_orders` with 4 stop-entry shorts
    - Clear `stop_loss_orders_hedge`
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
- Orders: 1 stop-loss at -1 (`stop_loss_full_long`), 4 stop-entry shorts ready at [-1, -2, -3, -4] (`enter_short_orders`)

**Price Advances to Unit +7**:
- Stop-loss triggered at +6 → Position now 100% cash
- Short window slides: stop-entry shorts now at [+3, +4, +5, +6]

**Retracement to Unit +4**:
- Stop-entry shorts at +6, +5 triggered → stop-losses added at +5, +4 to `stop_loss_orders_hedge`
- Orders: 2 stop-entry shorts [+3, +4], 2 stop-losses [+4, +5]
- Position: 50% short exposure

**Further Drop to Unit +2**:
- All stop-entry shorts triggered → 4 stop-losses in `stop_loss_orders_hedge`
- Orders: 4 stop-losses at [+1, +2, +3, +4]
- Position: Maximum short exposure (DECLINE phase)

**Recovery to Unit +5**:
- Stop-losses at +1, +2, +3 triggered → replaced with stop-entry shorts one unit behind
- Orders: 1 stop-loss [+4], 3 stop-entry shorts [+2, +3, +4]
- Position: 25% short remaining

**Full Recovery to Unit +7**:
- All stop-losses triggered → 100% cash with profits
- Place market buy order via `market_buy_full_long_orders` with all capital
- RESET triggered once long fills

### Key Order Management Rules (Hedge Wallet)

1. **Maintain 4-5 active orders** across different order types
2. **Order Management by Type**:
   - `stop_loss_full_long`: Trails at current-1 to exit long
   - `enter_short_orders`: 4 limit shorts trailing behind price
   - `stop_loss_orders_hedge`: Stop-losses added as shorts fill
   - `market_buy_full_long_orders`: Market order for re-entry
3. **Position Transitions**:
   - Long → Cash (via `stop_loss_full_long`)
   - Cash → Short (via `enter_short_orders`)
   - Short → Cash (via `stop_loss_orders_hedge`)
   - Cash → Long (via `market_buy_full_long_orders`)
4. **Windows slide automatically** based on price movement

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

## Practical Implementation Considerations

### Order Execution Handling

**Partial Fills**:
- If a stop-loss or limit order partially fills, treat it as fully executed for window management
- Place the replacement order immediately based on the partial execution
- Adjust fragment calculations for the remaining unfilled portion

**Order Rejections**:
- Common causes: Insufficient margin, price moved beyond limit, position size limits
- Response: Retry with adjusted parameters or skip to next unit level
- Maintain window integrity by ensuring 4 total orders remain active

**Network Disconnection Recovery**:
- On reconnection: Query all open orders and recent fills
- Reconstruct current phase based on active order types
- Resume sliding window management from current state
- No need to cancel/replace orders unless phase has changed

### Exchange-Specific Considerations

**Hyperliquid Specifics**:
- Minimum order size: Check current minimums for your selected asset
- Price tick size: Round all order prices to valid tick increments  
- Rate limits: Batch order operations when sliding windows
- WebSocket channels: Subscribe to order updates and price feeds
- **WebSocket Limitation**: Maximum 20 concurrent WebSocket channels, limiting strategy to 20 coins maximum

**Order Type Availability**:
- Verify stop-loss order support for your asset
- Confirm stop-entry orders for short positions are available
- Check if trailing stops can be used to automate window sliding

### State Recovery and Monitoring

**Phase Detection on Startup**:
- Query all open orders for each wallet
- Count stop-loss vs limit orders to determine current phase
- Check position size to confirm phase alignment
- Resume appropriate sliding window behavior

**Monitoring Requirements**:
- Track current unit position continuously
- Monitor order fill notifications in real-time
- Detect when windows need sliding (unit changes)
- Log all phase transitions for debugging

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

