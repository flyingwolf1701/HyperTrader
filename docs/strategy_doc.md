
# Advanced Hedging Strategy v4.2.0

## Core Philosophy

This is a bull market thesis strategy designed to profit in both directions while maintaining a long-term upward bias. The system uses automated execution to capture gains during retracements and amplify returns during recoveries, remaining profitable even during significant drawdowns.

The strategy features a simplified scaling system using fixed percentage chunks and uses WebSocket-driven price monitoring with CCXT exchange integration for real-time execution.

## Portfolio Architecture

### Simplified Position Management

The strategy starts with a **single long position** during the advance phase. Position splitting only occurs during retracements:

*   **ADVANCE Phase:** Single unified long position tracking peaks
*   **RETRACEMENT Phase:** Position splits into cash and shorts using 12% scaling chunks  
*   **RECOVERY Phase:** Cash and shorts are systematically bought back using 25% scaling

This approach eliminates the complexity of managing two separate allocation systems from the start.

### Unit-Based Tracking System

*   **Unit Definition:** A "unit" is a fixed, manually-defined price movement that is set on a per-asset basis. This gives the trader direct control over the strategy's sensitivity to market volatility.
*   **Control:** By adjusting the unit size, the strategy can be made more or less reactive. A smaller unit size makes the bot more sensitive to small price swings, while a larger unit size makes it less sensitive.
*   **Example:** For an asset like ARB trading at `$0.60`, a unit might be manually set to `$0.0025`. Every time the price moves up or down by this amount, the `currentUnit` is incremented or decremented.
*   **Execution:** Only whole unit movements trigger trading actions (e.g., no actions on 0.5 or 1.5 unit changes).

### Key Variables

*   `entryPrice`: The price at which the current tracking cycle began (updated when `peakUnit` or `valleyUnit` resets).
*   `currentUnit`: The current price distance from the `entryPrice`, measured in units.
*   `peakUnit`: The highest unit reached during an `ADVANCE` phase.
*   `valleyUnit`: The lowest unit reached during a `DECLINE` phase.
*   `longInvested`: Dollar amount in long positions.
*   `longCash`: Dollar amount held as cash (from retracement sales).
*   `hedgeShort`: Dollar amount in short positions (opened during deep retracements).

## Peak/Valley Tracking System

### Peak Tracking Rules

*   `peakUnit` is updated to `currentUnit` whenever a new high is made during ADVANCE phase
*   Peaks are tracked continuously while holding long positions
*   The `entryPrice` is updated when system resets, establishing a new reference price

### Valley Tracking Rules

*   `valleyUnit` is updated to `currentUnit` whenever a new low is made during DECLINE phase  
*   Valleys are tracked when short positions exist or cash is held from retracement sales

### System Reset Trigger

A full system reset occurs when the position returns to a unified long state:
1.  `hedgeShort` = $0 (no short positions)
2.  `longCash` = $0 (no cash positions)  
3.  All funds are back in `longInvested`

### Reset Process

*   Consolidate all funds into a single long position
*   Reset all tracking variables:
    *   `currentUnit = 0`
    *   `peakUnit = 0`  
    *   `valleyUnit = null`
*   Reset `entryPrice` to the current market price

## Four-Phase Trading System

### ADVANCE Phase

*   **Characteristics:** Single unified long position tracking new peaks
*   **Trigger:** When all funds are consolidated in long positions (no cash or shorts)
*   **Action:** Hold long position and track peak progression
*   **On First Decline:** Immediately sell first 12% chunk and transition to RETRACEMENT

### RETRACEMENT Phase

*   **Characteristics:** Position systematically scaled down using 12% chunks
*   **Trigger:** Any decline from an established peak
*   **Actions:**
    *   **Each Unit Down:** Sell 12% of total position value
    *   **Early Retracement:** Convert long position to cash
    *   **Deep Retracement:** Start opening short positions when long is exhausted
*   **Transition:** Move to DECLINE when all long positions are sold

### DECLINE Phase

*   **Characteristics:** All long positions sold, holding cash and/or short positions
*   **Trigger:** Long position reaches $0 (fully in cash/shorts)
*   **Action:** Hold defensive positions, track valley formation
*   **Valley Tracking:** Update `valleyUnit` on each new low

### RECOVERY Phase

*   **Characteristics:** Systematic re-entry using 25% of available funds per unit
*   **Trigger:** Any uptick from an established valley
*   **Actions:**
    *   **Each Unit Up:** Buy back 25% of available cash/shorts
    *   **Priority:** Cover short positions first, then buy long with cash
    *   **25% Scaling:** Works well with multiple "buckets" of defensive positions
*   **Transition:** Return to ADVANCE when fully re-invested

## Position Scaling Matrix

### RETRACEMENT Scaling (12% Chunks)

| Units from Peak | Long Position | Cash Position | Short Position | Action                    |
| :-------------- | :------------ | :------------ | :------------- | :------------------------ |
| 0 units         | 100%          | 0%            | 0%             | Hold (ADVANCE)            |
| -1 unit         | 88%           | 12%           | 0%             | Sell 12% → Cash           |
| -2 units        | 76%           | 24%           | 0%             | Sell 12% → Cash           |
| -3 units        | 64%           | 36%           | 0%             | Sell 12% → Cash           |
| -4 units        | 52%           | 48%           | 0%             | Sell 12% → Cash           |
| -5 units        | 40%           | 60%           | 0%             | Sell 12% → Cash           |
| -6 units        | 28%           | 72%           | 0%             | Sell 12% → Cash           |
| -7 units        | 16%           | 84%           | 0%             | Sell 12% → Cash           |
| -8 units        | 4%            | 96%           | 0%             | Sell 12% → Cash           |
| -9 units        | 0%            | 88%           | 12%            | Sell remaining → Short    |
| -10+ units      | 0%            | Variable      | Variable       | DECLINE phase             |

### RECOVERY Scaling (25% of Available Funds)

| Units from Valley | Action                                     | Priority                     |
| :---------------- | :----------------------------------------- | :--------------------------- |
| +1 unit           | Buy 25% of (cash + shorts)                | Cover shorts first           |
| +2 units          | Buy 25% of remaining (cash + shorts)      | Cover shorts first           |
| +3 units          | Buy 25% of remaining (cash + shorts)      | Cover shorts first           |
| +4 units          | Buy 25% of remaining (cash + shorts)      | Then buy long with cash      |
| +N units          | Continue until fully re-invested          | Return to ADVANCE when done  |

## Technical Implementation

*   **Real-Time Price Monitoring:** Continuous price feeds via WebSocket, real-time unit calculation, and automatic trigger detection
*   **CCXT Trading Integration:** Direct market order execution with HyperLiquid, position synchronization, and robust error handling
*   **State Management:** Simplified allocation tracking with automatic state updates after successful order execution
*   **Position Synchronization:** Automatic reconciliation between internal state and actual exchange positions on startup

## Key Simplifications in v4.2.0

*   **Unified Starting Position:** Eliminates complex dual-allocation setup - starts with single long position
*   **Fixed Percentage Chunks:** 12% retracement scaling and 25% recovery scaling for predictable behavior
*   **Clear Phase Transitions:** Each phase has distinct characteristics and triggers
*   **Automatic State Updates:** Order execution immediately updates internal allocation tracking

## Edge Case Handling

*   **Gap Events:** System recalculates position based on new price reality rather than chasing missed trades
*   **State Recovery:** Automatic synchronization with exchange positions on restart
*   **Partial Fills:** System tracks actual fills vs. intended allocations and adjusts subsequent trades accordingly

## Performance Characteristics

*   **Mathematical Advantages:** Profitable in both up and down trends with systematic scaling and risk management
*   **Expected Outcomes:** Full participation in bull markets, defensive cash/short positions in bear markets, systematic re-entry during recoveries
*   **Simplified Logic:** Reduced complexity while maintaining core strategy benefits

## Risk Management

*   **Real-time Monitoring:** Complete audit trail of all decisions and executions with detailed logging
*   **Position Limits:** 12% maximum position reduction per unit movement during retracements
*   **Defensive Positioning:** Systematic conversion to cash and shorts during declining markets
