# Advanced Hedging Strategy v5.0.0 (Simplified Implementation)

## Core Philosophy

This is a bull market thesis strategy designed to profit in both directions while maintaining a long-term upward bias. The system uses automated execution to capture gains during retracements and amplify returns during recoveries, remaining profitable even during significant drawdowns.

The strategy features a critical peak/valley reset mechanism and uses WebSocket-driven price monitoring with CCXT exchange integration for real-time execution.

## Portfolio Architecture

### Unified Position Management (v5.0.0)

*   **Single Position Tracking:** The system manages one unified position that can range from fully long to partially short
*   **File-Based State:** All strategy state is persisted in `strategy_state.json` - no database required
*   **Cumulative Position Changes:** Each phase transition applies cumulative adjustments based on distance from peak/valley
*   **Net Position:** Position can go negative (short) during extreme declines



### Unit-Based Tracking System

*   **Unit Definition:** A "unit" is a fixed, manually-defined price movement that is set on a per-asset basis. This gives the trader direct control over the strategy's sensitivity to market volatility.
*   **Control:** By adjusting the unit size, the strategy can be made more or less reactive. A smaller unit size makes the bot more sensitive to small price swings, while a larger unit size makes it less sensitive.
*   **Example:** For an asset like ARB trading at `$0.60`, a unit might be manually set to `$0.0025`. Every time the price moves up or down by this amount, the `currentUnit` is incremented or decremented.
*   **Execution:** Only whole unit movements trigger trading actions (e.g., no actions on 0.5 or 1.5 unit changes).

### Key Variables

*   `entry_price`: The initial price when strategy starts
*   `current_unit`: The current price distance from the `entry_price`, measured in units
*   `peak_unit`: The highest unit reached during an `ADVANCE` phase
*   `valley_unit`: The lowest unit reached during a `DECLINE` phase  
*   `current_long_position`: Net dollar position (positive = long, negative = short)
*   `decline_portion`: Fixed amount per unit = `position_size_usd / 12`
*   `position_size_usd`: Total capital allocated to strategy
*   `leverage`: Leverage multiplier for position sizing

## Critical Peak/Valley Reset Mechanism

### Peak Tracking Rules

*   `peak_unit` is continuously updated to the highest `current_unit` during ADVANCE phase
*   Used to calculate distance for RETRACEMENT trades

### Valley Tracking Rules

*   `valley_unit` is continuously updated to the lowest `current_unit` during DECLINE phase
*   Used to calculate distance for RECOVERY trades


### System Reset Trigger

*   Occurs when returning to ADVANCE phase from RECOVERY
*   `entry_price` updates to current price for new cycle
*   `peak_unit` resets to current unit
*   `valley_unit` resets to null


## Four-Phase Trading System (v5.0.0 Simplified)

### ADVANCE Phase


### RETRACEMENT Phase

*   **Characteristics:** Price declining from peak, executing progressive sells and shorts
*   **Trigger:** First decline from established peak
*   **Actions:** 
    *   Execute trades based on cumulative distance from peak
    *   Position reduces progressively and can go negative (short)
    *   Uses `decline_portion` (position_size/12) for scaling


### DECLINE Phase

*   **Characteristics:** Holding defensive cash/short positions
*   **Trigger:** Long position exhausted (position ≤ 0)
*   **Action:** Track valley formation, wait for recovery signal

#### (OLD)


### RECOVERY Phase

*   **Characteristics:** Price recovering from valley, systematic re-entry
*   **Trigger:** First uptick from established valley
*   **Actions:**
    *   Buy back 25% of available cash per unit up
    *   Cover shorts and re-establish long positions
    *   System resets to ADVANCE when fully invested

## Position Scaling Logic (v5.0.0 - Cumulative)

### RETRACEMENT Scaling (From Peak)

The position changes are **cumulative** - each tier adds to the previous reductions:

```python
decline_portion = position_size_usd / 12  # Fixed amount per scaling unit

# Calculate target position based on units from peak
target_position = position_size_usd  # Start at full long

if units_from_peak >= 1:
    target_position -= 2 * decline_portion  # -$833 at $5000 size
if units_from_peak >= 2:
    target_position -= 3 * decline_portion  # Additional -$1250 (total -$2083)
if units_from_peak >= 3:
    target_position -= 3 * decline_portion  # Additional -$1250 (total -$3333)
if units_from_peak >= 4:
    target_position -= 3 * decline_portion  # Additional -$1250 (total -$4583)
if units_from_peak >= 5:
    target_position = -position_size_usd * 0.33  # Emergency: 33% short
```

## Position Scaling Matrix (v5.0.0)

### RETRACEMENT Position Targets (Cumulative from Peak)

| Units from Peak | Target Position | Net Change | Cumulative Change | Phase |
| :-------------- | :-------------- | :--------- | :---------------- | :------------ |
| 0 units         | 100% ($5000)    | $0         | $0                | ADVANCE |
| -1 unit         | 83% ($4167)     | -$833      | -$833             | RETRACEMENT |
| -2 units        | 58% ($2917)     | -$1250     | -$2083            | RETRACEMENT |
| -3 units        | 33% ($1667)     | -$1250     | -$3333            | RETRACEMENT |
| -4 units        | 8% ($417)       | -$1250     | -$4583            | RETRACEMENT |
| -5+ units       | -33% (-$1650)   | -$2067     | -$6650            | RETRACEMENT |

*Example based on $5000 position size*




### RECOVERY Scaling (From Valley)

| Units from Valley | Action | Amount | Target Position | Phase |
| :---------------- | :----- | :----- | :-------------- | :-------- |
| +1 unit           | Buy    | 25% of cash | Move toward long | RECOVERY |
| +2 units          | Buy    | 25% of cash | Continue buying  | RECOVERY |
| +3 units          | Buy    | 25% of cash | Continue buying  | RECOVERY |
| +4 units          | Buy    | 25% of cash | Near full long   | RECOVERY |
| Full long reached | Reset  | -           | 100% long        | ADVANCE |

## Technical Implementation (v5.0.0)

### File-Based State Management
*   **Storage:** All state persisted in `strategy_state.json`
*   **No Database:** Simplified architecture without database dependencies
*   **Atomic Updates:** State saved after each trade execution

### Exchange Integration  
*   **CCXT Library:** Direct integration with HyperLiquid via CCXT
*   **Market Orders:** All trades executed as market orders with slippage protection
*   **Position Tracking:** Real-time position synchronization with exchange

### API Endpoints
*   `/strategy/start` - Initialize new strategy with parameters
*   `/strategy/update` - Check price and execute trades based on unit changes
*   `/strategy/status` - Get current state and position information
*   `/strategy/stop` - Stop strategy and remove state file

## Edge Case Handling

*   **Gap Events:** If the price gaps, the system recalculates the position based on the new price reality rather than chasing missed trades.
*   **Extreme Volatility:** Choppy trading rules activate automatically for tighter position management.
*   **Partial Fills:** The system tracks actual fills vs. intended allocations and adjusts subsequent trades accordingly.

## Key Improvements in v5.0.0

### Simplified Architecture
*   **Database Removed:** File-based state management for reliability
*   **Single Position:** Unified position tracking instead of dual allocations
*   **Fixed Math:** Simple `position_size / 12` calculation for decline portions

### Cumulative Scaling
*   **Proper Accumulation:** Each tier adds to previous reductions
*   **Short Positions:** System can go net short during extreme declines
*   **Clear Targets:** Explicit position targets at each unit level

### Immediate Execution
*   **Phase Transition Trades:** Trades execute immediately on phase changes
*   **No Waiting:** Removed confirmation delays for faster response
*   **Unit-Based Triggers:** Clean integer unit movements trigger actions

## Testing & Verification

### Test Mode
*   **Test Price Override:** Set `test_price` in state for manual testing
*   **Simulated Scenarios:** Force price movements to test all phases
*   **Exchange Verification:** Check actual positions match expected state

### Example Test Commands
```bash
# Start strategy
curl -X POST "http://localhost:8000/api/v1/strategy/start" \
  -d '{"symbol": "ETH/USDC:USDC", "position_size_usd": 5000, "unit_size": 0.5, "leverage": 25}'

# Update (check price and execute trades)
curl -X POST "http://localhost:8000/api/v1/strategy/update"

# Check status
curl "http://localhost:8000/api/v1/strategy/status"
```
