# Long-Biased Grid Trading Strategy v11.2.0

## 1. Core Philosophy

This is a bull-market thesis strategy engineered to capitalize on price volatility while maintaining a long-term upward bias. The ultimate goal is to accumulate a position at the lowest possible price by systematically taking profits during price retracements and compounding returns during recoveries.

The strategy is centered around a dynamic grid system that continuously maintains four active orders trailing the current price. This "sliding window" approach allows for fully automated, seamless execution in both trending and ranging markets without manual intervention.

## 2. User Initialization and Setup

### Required User Inputs

Before activation, the user must define the following parameters:

- **Wallet Allocation**: The total USD amount to be dedicated to this strategy.

- **Leverage Setting**: The leverage multiplier to be applied to the allocation (e.g., 10x).

- **Asset Selection**: The specific coin/token to be traded (e.g., ETH, BTC, SOL).

- **Unit Size**: The price movement increment that defines one "unit." This is a fixed dollar amount (e.g., $100 for BTC, $1 for SOL).

### Fragment Calculation

The total leveraged position is divided into four equal parts, or "fragments."

- **Position Fragment**: Each fragment represents 25% of the total position.

- **Sell Fragments**: Sells are executed based on a fixed amount of the **coin** (e.g., selling 0.1 ETH). This ensures a consistent reduction of the asset position regardless of price.

- **Buy Fragments**: Buys are executed based on a fixed **USD** amount (e.g., buying $2,500 worth of ETH). This ensures consistent capital deployment.

## 3. Initial Order Placement

The strategy begins with a full position in the selected asset.

1. **Establish Position**: A market buy is executed for the full Wallet Allocation multiplied by the Leverage Setting.

2. **Set Anchor Price**: The execution price of the initial buy order is recorded and established as current_unit = 0.

3. **Place Initial Grid**: The system immediately places four stop-loss sell orders, each for a 25% position fragment, at prices corresponding to current_unit - 1, current_unit - 2, current_unit - 3, and current_unit - 4.

At this point, the strategy is fully active and the automated, event-driven logic begins.

## 4. Core Logic: The Event-Driven Whipsaw-Resistant Grid

The strategy's foundation is a sophisticated event-driven system that distinguishes between genuine trends, simple reversals, and market noise (whipsaws). The system prioritizes placing new, relevant orders before cleaning up old ones.

### The Fundamental Rule

**The system's target state is to have exactly four active orders.** Due to the high-priority "place-then-cancel" logic, there may be brief periods with more than four orders while obsolete orders are being asynchronously cancelled.

### Directional Event Logic

The bot's actions are determined by comparing the current direction of price movement to the previous direction.

- If current_unit > previous_unit, the current_direction is 'up'.

- If current_unit < previous_unit, the current_direction is 'down'.

### 1. Trending Market (Grid Sliding)

This logic applies when the market continues in the same direction (current_direction equals previous_direction). The active orders are managed in sorted lists, trailing_stop and trailing_buy, to efficiently identify the oldest order.

- **Trending Up:** The bot executes the following sequence:

1. **Place New Order:** A new stop-loss sell order is placed at current_unit - 1.

2. **Append to List:** The new unit is appended to the trailing_stop list, which is kept sorted. For example, if the list was [6, 7, 8, 9] and the new order is at unit 10, the list becomes [6, 7, 8, 9, 10].

3. **Check Length:** The bot checks if the length of the list is now greater than four.

4. **Pop and Cancel:** If it is, the bot removes the first element (the oldest order with the lowest unit number) from the list. The unit from this popped element is then used to asynchronously cancel the now-obsolete order.

2. **Trending Down:** The bot follows a similar sequence for buy orders:

1. **Place New Order:** A new stop-entry buy order is placed at current_unit + 1.

2. **Append to List:** The new unit is appended to the trailing_buy list. For example, if the list was [10, 11, 12, 13] and the new order is at unit 9, the list becomes [9, 10, 11, 12, 13].

3. **Check Length:** The bot checks if the length of the list is now greater than four.

4. **Pop and Cancel:** If it is, the bot removes the last element (the oldest order with the highest unit number) from the list and asynchronously cancels it.

### 2. Standard Reversal (State-Managed Replacement)

This logic is triggered by a UnitChangeEvent that signals a change in market direction (current_direction is different from previous_direction). A reversal implies an order has been executed. The bot's action is immediate, while the subsequent fill notification from the exchange serves as a confirmation to update the ledger.

- **Reversal Down (up -> down):** A UnitChangeEvent signals a downward reversal, implying a stop-loss sell has just been filled at the current_unit.

1. **Place Replacement:** The bot's highest priority is to immediately place a new stop-entry buy order at current_unit + 1 (e.g., at unit 10, since current_unit is now 9).

2. **Update State & Ledger:** The bot immediately updates all its internal state records.

- The trailing_stop list is updated: the unit of the filled sell order (e.g., unit 9) is removed.

- The trailing_buy list is updated: the new buy order's unit (e.g., unit 10) is added.

- The new order's information (order_id, type, status='active') is appended to the lists within the PositionMap for its unit (unit 10).

- A new entry is added to the OrderIDMap linking the new order's ID to its unit.

- **Confirm & Finalize Log:** The subsequent fill notification from the WebSocket arrives. The bot uses the order_id from the fill to look up the unit in the OrderIDMap. It then finds that specific order in the PositionMap's history and updates its status from 'active' to 'filled', finalizing the historical record.

- **Reversal Up (down -> up):** A UnitChangeEvent signals an upward reversal, implying a stop-entry buy has just been filled at the current_unit.

1. **Place Replacement:** The bot immediately places a new stop-loss sell order at current_unit - 1 (e.g., at unit 9, since current_unit is now 10).

2. **Update State & Ledger:** The bot updates its internal state.

- The trailing_buy list is updated: the unit of the filled buy order (e.g., unit 10) is removed.

- The trailing_stop list is updated: the new sell order's unit (e.g., unit 9) is added.

- The new order's details are recorded in the PositionMap for unit 9.

- The new order's ID is linked to its unit in the OrderIDMap.

- **Confirm & Finalize Log:** The fill notification is used to find the corresponding entry in the PositionMap and update its status to 'filled'.

### 3. Whipsaw Identification and Handling

A whipsaw is identified by a specific three-step price movement pattern (e.g., 10 -> 9 -> 10).

- **Step 1: Initial Reversal (10 -> 9):** The bot executes the standard "Reversal Down" logic, placing a buy order at unit 10. The grid now has 3 sells and 1 buy.

- **Step 2: Whipsaw Trigger (9 -> 10):** The price immediately moves back up, filling the newly placed buy order. The bot recognizes this A -> B -> A pattern and enters a **paused state**. It intentionally **does not** place the standard replacement sell order. The grid is now temporarily down to three active sell orders.

- **Step 3: Post-Whipsaw Resolution:** The bot waits for the next unit change to determine the true market direction.

- **Trend Confirmation (10 -> 11):** The original uptrend is confirmed. The bot restores the grid by placing two new sell orders (at units 10 and 9) and then cancelling the oldest order to return to a 4-order grid.

- **Reversal Confirmation (10 -> 9):** If the price reverses down again after a whipsaw, the bot confirms a new downtrend. It then places a new sell order at the bottom of the ideal grid, at current_unit - 4, to restore the 4-order grid.

## 5. Continuous Compounding and Dynamic Sizing

The strategy achieves continuous compounding by immediately reinvesting realized PnL. This is managed through a clear separation of state variables, ensuring calculations are accurate and robust.

### Core State Variables for Sizing and Tracking

The system relies on three key variables to manage its size over time:

- **initial_position_value_usd**: A static variable set only once at the beginning of the trading session. It represents the initial leveraged value of the position (e.g., $10,000). This serves as a stable baseline for all compounding calculations.

- **realized_pnl**: A cumulative tracker. After every sell order is filled, the PnL from that specific trade is calculated and added to this variable. This variable grows over time as trades are closed.

- **position_size**: The current quantity of the asset held, as reported by the exchange. This is the source of truth for the bot's sellable inventory.

### Buy-Side Compounding (Reinvesting PnL)

The logic for sizing buy orders is designed to immediately put realized profits to work, increasing the bot's buying power.

1. Calculate Updated Value: When a sell order is filled, the bot calculates an updated_position_value on the fly. This is a temporary, derived variable: \
updated_position_value = initial_position_value_usd + realized_pnl

2. Calculate New Fragment Size: The bot then calculates the new, larger fragment size for buy orders: \
new_buy_fragment = updated_position_value / 4

3. **Execution and Modification:**

- All **new** buy orders placed after this point will use the new_buy_fragment size.

- Previous orders may have a different size, and that is perfectly fine. It is ok if some money isn’t reinvested right away. Crucially, more will be invested at lower prices as the grid naturally rotates.

### Sell-Side Sizing (Self-Correcting Grid)

The logic for sizing sell orders is designed to be dynamically accurate, ensuring the bot sells a precise fraction of what it currently holds.

1. **Dynamic Calculation:** The size for all **new** sell orders is calculated on-the-fly, not based on the original position size.

2. Fragment Formula: The position_size_fragment is calculated based on the current position_size and the number of active sell orders in the trailing_stop list: \
fragment = position_size / trailing_stop.length

3. **Safety Cap:** To ensure the formula behaves correctly when the grid is full, the maximum divisor is capped at 4. If trailing_stop.length >= 4, the formula becomes fragment = position_size / 4.

## 6. Implementation and Risk

### Architectural Components

To implement the event-driven logic, the system relies on specialized data structures with clearly defined responsibilities.

- **Unit Tracker**: A pure price interpreter whose sole responsibility is to translate the raw price feed from the WebSocket. It maintains the directional state variables (current_unit, previous_unit, current_direction, previous_direction) and emits a UnitChangeEvent whenever the price crosses a unit boundary. It has no knowledge of orders or positions.

- **Position Map**: This is the primary historical ledger for the system. It is structured as a dictionary where each key is an integer representing a unit. The value for each unit contains the price and a complete history of all orders placed at that level. To accommodate multiple orders per unit over time, the order details are stored in lists. It is initialized with a buffer of units (e.g., -10 to +10) and dynamically expands as the price trends into new territory.

- **Data Shape:** \
Dict[unit: int, { \
    "price": Decimal, \
    "order_ids": List[str], \
    "order_types": List[str], \
    "order_statuses": List[str] \
}] \


- **Order ID Map**: This is a companion dictionary that serves as a high-speed index for instantaneous lookups. This allows the system to find an order's corresponding unit from a fill notification without needing to perform slow searches through the PositionMap.

- **Data Shape:** \
Dict[order_id: str, unit: int] \


### General Implementation Notes

- **Execution Priority**: The bot uses a "place-then-cancel" model. Placing new, necessary orders is always the highest priority. Cancelling old, obsolete orders is a lower-priority, asynchronous task.

- **Order List Management**: The active sell and buy orders are managed as sorted lists. When a new order is added, if the list length exceeds four, the oldest order is popped from the list and scheduled for cancellation.

- **Resilience**: On startup, the system must query open orders to reconstruct its state.
