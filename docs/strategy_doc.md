# Advanced Hedging Strategy v4.1.14

## Core Philosophy

This is a bull market thesis strategy designed to profit in both directions while maintaining a long-term upward bias. The system uses automated execution to capture gains during retracements and amplify returns during recoveries, remaining profitable even during significant drawdowns.

The strategy features a critical peak/valley reset mechanism and uses WebSocket-driven price monitoring with CCXT exchange integration for real-time execution.

## Portfolio Architecture

### Two Independent Allocation Systems

*   **Long Allocation:** Patient capital that waits for optimal entries.
    *   Requires 2-unit confirmation before scaling positions.
    *   Focuses on longer-term trend reversals.
    *   Starts at 50% of total margin but diverges based on performance.
*   **Hedge Allocation:** Active protection capital that responds immediately.
    *   Immediate 1-unit response to price movements.
    *   Provides downside protection and profits from corrections.
    *   Starts at 50% of total margin but diverges based on performance.

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
*   `longCash`: Dollar amount held as cash.
*   `hedgeLong`: Dollar amount in hedge long positions.
*   `hedgeShort`: Dollar amount in hedge short positions.

## Critical Peak/Valley Reset Mechanism

### Peak Tracking Rules

*   `peakUnit` is set to `null` when `longInvested` is 0 (no long positions to track peaks from).
*   When `longInvested > 0`, `peakUnit` is updated to `currentUnit` whenever a new high is made.
*   The `entryPrice` is updated when `peakUnit` resets, establishing a new reference price.

### Valley Tracking Rules

*   `valleyUnit` is set to `null` when `hedgeShort` is 0 (no short positions to track valleys from).
*   When `hedgeShort > 0`, `valleyUnit` is updated to `currentUnit` whenever a new low is made.

### System Reset Trigger

A full system reset only occurs when **BOTH** of these conditions are met:
1.  `hedgeShort` = $0 (no short positions)
2.  `longCash` = $0 (no cash positions)

### Reset Process

*   Split the total portfolio value 50/50 between the Long and Hedge allocations.
*   Reset all tracking variables:
    *   `currentUnit = 0`
    *   `peakUnit = 0`
    *   `valleyUnit = null`
*   Reset `entryPrice` to the current market price.

## Four-Phase Trading System

### ADVANCE Phase

*   **Characteristics:** Both allocations are 100% long, tracking new peaks.
*   **Trigger:** When both allocations are fully long.
*   **Action:** Hold positions and track peak progression.

### RETRACEMENT Phase

*   **Characteristics:** The price has declined from a peak, and confirmation rules are active. The hedge allocation scales immediately, while the long allocation waits for confirmation.
*   **Trigger:** Any decline from an established peak.
*   **Actions:**
    *   **Hedge:** Immediately scales its position by 25% for each unit of movement.
    *   **Long:** Waits for a 2-unit confirmation before scaling by 25% per confirmed unit.

### DECLINE Phase

*   **Characteristics:** The long allocation is fully in cash for protection, and the hedge allocation is fully short to profit from the decline.
*   **Trigger:** The long allocation reaches 0% invested.
*   **Action:** Hold positions, allowing short positions to compound gains during major corrections.

### RECOVERY Phase

*   **Characteristics:** The price is recovering from a valley, triggering a systematic re-entry. The hedge allocation unwinds its shorts immediately, while the long allocation re-enters after confirmation.
*   **Trigger:** Any recovery from an established valley.
*   **Actions:**
    *   **Hedge:** Immediately unwinds shorts and scales back into a long position.
    *   **Long:** Waits for a 2-unit confirmation before systematically re-entering.

## Choppy Trading Detection & Management

### Automatic Detection

Choppy trading rules are triggered when either allocation is partially invested:
*   **Long allocation:** `0% < longInvested < 100%`
*   **Hedge allocation:** `0% < hedgeLong < 100%` AND `hedgeShort > 0%`

### Choppy Trading Rules

*   **No Confirmation Delays:** 1-unit movements trigger immediate 25% position changes for both allocations.
*   **Faster Response:** Protects against rapid oscillations.
*   **Tighter Trading:** Minimizes exposure during uncertain periods.

## Position Scaling Matrix

### Long Allocation Scaling (Confirmation Required)

| Units from Peak | Long Position | Action     | Trigger                        |
| :-------------- | :------------ | :--------- | :----------------------------- |
| 0 units         | 100% Long     | Hold       | Peak tracking                  |
| -1 unit         | 100% Long     | **WAIT**   | No action (needs confirmation) |
| -2 units        | 75% Long      | Sell 25%   | Confirmed decline              |
| -3 units        | 50% Long      | Sell 25%   | Continued decline              |
| -4 units        | 25% Long      | Sell 25%   | Significant decline            |
| -5 units        | 0% Long       | Sell 25%   | Full cash (DECLINE phase)      |

### Hedge Allocation Scaling (Immediate Response)

| Units from Peak | Hedge Long | Hedge Short | Action              | Phase         |
| :-------------- | :--------- | :---------- | :------------------ | :------------ |
| 0 units         | 100% Long  | 0% Short    | Hold                | ADVANCE       |
| -1 unit         | 75% Long   | 25% Short   | Sell 25% → Short    | RETRACEMENT   |
| -2 units        | 50% Long   | 50% Short   | Sell 25% → Short    | RETRACEMENT   |
| -3 units        | 25% Long   | 75% Short   | Sell 25% → Short    | RETRACEMENT   |
| -4 units        | 0% Long    | 100% Short  | Sell 25% → Short    | DECLINE       |

### Recovery Scaling (From Valley)

| Units from Valley | Long Position | Long Action | Hedge Position        | Hedge Action        | Phase               |
| :---------------- | :------------ | :---------- | :-------------------- | :------------------ | :------------------ |
| +1 unit           | 0% Long       | **WAIT**    | 25% Long / 75% Short  | Cover 25% → Long    | RECOVERY            |
| +2 units          | 25% Long      | Buy 25%     | 50% Long / 50% Short  | Cover 25% → Long    | RECOVERY            |
| +3 units          | 50% Long      | Buy 25%     | 75% Long / 25% Short  | Cover 25% → Long    | RECOVERY            |
| +4 units          | 75% Long      | Buy 25%     | 100% Long / 0% Short  | Cover 25% → Long    | RECOVERY            |
| +5 units          | 100% Long     | Buy 25%     | 100% Long / 0% Short  | Hold Long           | ADVANCE → **RESET** |

## Technical Implementation

*   **Real-Time Price Monitoring:** Continuous price feeds via WebSocket, real-time unit calculation, and automatic trigger detection.
*   **CCXT Trading Integration:** Direct market order execution, position synchronization, and robust error handling.
*   **State Management:** Automatic logic for peak/valley resets, allocation tracking, confirmation delays, and choppy market detection.

## Edge Case Handling

*   **Gap Events:** If the price gaps, the system recalculates the position based on the new price reality rather than chasing missed trades.
*   **Extreme Volatility:** Choppy trading rules activate automatically for tighter position management.
*   **Partial Fills:** The system tracks actual fills vs. intended allocations and adjusts subsequent trades accordingly.

## Performance Characteristics

*   **Mathematical Advantages:** Aims to be profitable in both up and down trends, with adaptive scaling and systematic risk management.
*   **Expected Outcomes:** Full participation in bull markets, profit from shorts in bear markets, minimized whipsaw in choppy markets, and systematic re-entry during recoveries.
*   **Reset Benefits:** A system reset provides a fresh start, prevents anchoring to old price levels, and allows previous gains to become the new base capital.

## Risk Management

*   **Monitoring Systems:** Real-time alerts, system health checks, and a complete audit trail of all decisions and executions.

## User Interface & Controls

*   **Dashboard Elements:** Live display of the current phase, unit distance, allocation status, P&L, reset history, and trade log.
*   **Manual Controls:** Emergency stop, thesis override, leverage adjustment, and a manual reset trigger.
