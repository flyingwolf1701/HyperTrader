# Advanced Hedging Strategy v7.0.3

## Core Philosophy

This is a bull market thesis strategy engineered to capitalize on price movements in both directions while maintaining a long-term upward bias. The system leverages automated execution on the Hyperliquid platform to systematically take profits during price retracements and compound returns during recoveries. The core logic is designed to remain resilient and profitable even through significant market volatility and drawdowns.

The strategy is centered around a dynamic four-phase system (Advance, Retracement, Decline, Recovery) and a crucial reset mechanism that re-calibrates the system after a full cycle, allowing profits to compound into the new base capital.

## Portfolio Architecture

### Position Management

For each asset, the strategy manages positions on Hyperliquid where multiple orders in the same direction are automatically consolidated. At any given time, the strategy may hold:

- **One long position** (if any long orders exist) - consolidated with averaged entry price
- **One short position** (if any short orders exist) - consolidated with averaged entry price  
- **Cash reserves** - undeployed funds available for new positions

During different phases, the portfolio composition varies:
- **ADVANCE/RESET phases**: 100% long position
- **RETRACEMENT phase**: Reducing long position while building short position
- **DECLINE phase**: Short position + cash reserves
- **RECOVERY phase**: Closing short position while rebuilding long position

### Leverage and Allocation

**Maximum Leverage:** All orders are placed utilizing the maximum leverage available for the specific asset (25x for ETH on Hyperliquid). This means the required margin is a fraction of the notional position size (e.g., a $1,000 notional position with 25x leverage requires $40 of margin).

**Position Allocation:**

- `initial_notional_allocation`: A fixed dollar amount representing the notional value of the position at the start of a new trade cycle
- `initial_margin_allocation`: The actual margin committed at the start (notional ÷ leverage)
- `current_notional_allocation`: The real-time notional value of the position. This value fluctuates as the strategy executes and will ideally grow over time through compound returns
- `current_margin_allocation`: The real-time margin value, which is reset during the RESET mechanism

### Unit-Based Tracking System

**Unit Definition:** A "unit" is a manually defined price movement (e.g., $25.00 for ETH) that serves as the fundamental trigger for all strategic actions. The `unit_size` gives the trader direct control over the strategy's sensitivity to market volatility.

**Execution:** Trading actions are only triggered upon the completion of a full unit movement.

> **Post-MVP Note:** For future versions, the `unit_size` could become dynamic. It could adjust based on the current trading phase or other market conditions, such as stochastic RSI or trading volume, to make the strategy more adaptive.

## Key Variables

- `unit_size`: The trader-defined price movement that constitutes one unit
- `entry_price`: The average entry price of the position, as calculated and managed by Hyperliquid
- `current_unit`: The current price distance from the entry_price, measured in units. Initialized at 0
- `peak_unit`: The highest unit reached during an ADVANCE phase. Initialized at 0 and updated as new highs are made
- `valley_unit`: The lowest unit reached during a DECLINE phase. Initialized at 0 and updated as new lows are made
- `position_fragment_usd`: Calculated during the ADVANCE phase as 12% of the current total notional position value. This variable defines the USD size of scaling actions
- `position_fragment_eth`: The ETH amount corresponding to the position fragment, locked at peak values
- `hedge_fragment`: Calculated during the RECOVERY phase as 25% of the current total short position value (including unrealized P&L). This variable defines the size of scaling actions during the RECOVERY phase

## Trading Pattern: USD Buy, ETH Sell

The strategy employs a sophisticated trading pattern designed for optimal scaling:

**Buying (Position Building):**
- All long position entries use USD amounts for consistent sizing
- Recovery purchases use USD amounts to ensure consistent capital deployment
- Short position entries use USD amounts for consistent notional values

**Selling (Position Scaling):**
- Long position reductions use ETH amounts for consistent scaling regardless of price
- Short position closures use ETH amounts based on current hedge fragment calculations

This pattern ensures that:
- Retracement scaling remains consistent (same ETH amounts sold each time)
- Recovery purchases grow with short position profits (larger USD amounts as shorts become profitable)
- Compound growth is captured through the USD buy amounts increasing over time

## Short Position Tracking

During the RETRACEMENT phase, multiple short orders are placed which Hyperliquid automatically consolidates into a single short position with an averaged entry price. The strategy tracks:
- Total USD amount shorted across all retracement actions
- Hyperliquid's calculated average entry price for the consolidated position
- Total ETH amount of the consolidated short position
- Current unrealized P&L based on the averaged entry price

This simplified approach enables:
- Accurate P&L calculation using Hyperliquid's position data
- Hedge fragment calculation based on current short position value
- Compound growth through short profits feeding into recovery purchases

## The Four-Phase Trading System

### 1. ADVANCE Phase

This is the initial state upon entering a trade, assuming a bullish outlook.

**Condition:** Portfolio holds only a long position (100% long).

**Actions:**
- As the price increases by one `unit_size`, `current_unit` and `peak_unit` are both incremented by +1
- When a NEW PEAK is reached, the system calculates and LOCKS `position_fragment_usd` (12% of current notional position value) and `position_fragment_eth` (the corresponding ETH amount)
- The fragment values remain locked for the entire retracement cycle to ensure consistent scaling
- The system remains in the ADVANCE phase as long as the price continues to make new highs

### 2. RETRACEMENT Phase

This phase is triggered when the price falls from its peak.

**Trigger:** The price drops one unit from the established `peak_unit`.

**Logic:** The system executes a series of pre-defined actions based on the number of units the price has fallen from the peak (`current_unit - peak_unit`).

| Units from Peak | Action | Trading Pattern |
|-----------------|--------|-----------------|
| -1 | • Sell 1 `position_fragment_eth` of the long position<br>• Open a new short position equal to 1 `position_fragment_usd` | ETH sell, USD short |
| -2 | • Sell 2 `position_fragment_eth` of the long position<br>• Add 1 `position_fragment_usd` to short position | ETH sell, USD short |
| -3 | • Sell 2 `position_fragment_eth` of the long position<br>• Add 1 `position_fragment_usd` to short position | ETH sell, USD short |
| -4 | • Sell 2 `position_fragment_eth` of the long position<br>• Add 1 `position_fragment_usd` to short position | ETH sell, USD short |
| -5 | • Sell remaining long position at market price<br>• Hold proceeds in cash | Complete long exit |
| -6 & below | Enters the DECLINE phase | Portfolio: Short position + Cash reserves |

**Key Mechanics:**
- ETH amounts sold remain constant (locked from peak), ensuring consistent scaling
- USD amounts for shorts remain constant, ensuring consistent notional sizing
- As price drops, selling the same ETH amount yields less USD, while shorting the same USD amount requires more ETH
- Each short position is tracked individually for accurate P&L calculation

**Reversals:** If the price moves back up during this phase, the system executes the exact opposite of the last action. Special case: if reversing from -6 back to -5, buy long position worth 1 `position_fragment_usd` (rather than the smaller amount that was actually sold at -5).

### 3. DECLINE Phase

This phase is triggered after a significant retracement, where the portfolio is now defensive and positioned to profit from continued downtrend.

**Trigger:** The system has completed the retracement sequence.

**Condition:** Portfolio holds short position and cash reserves (no long position).

**Actions:**
- As the price continues to fall, `current_unit` is decremented, and `valley_unit` is updated to match `current_unit`, tracking the new low
- The consolidated short position accumulates profit as price drops below the averaged entry price
- If the price begins to recover (`current_unit` increments), the system calculates `hedge_fragment` as 25% of the current total value of the short position (including unrealized P&L based on Hyperliquid's averaged entry price)

### 4. RECOVERY Phase

This phase is triggered when the price shows a confirmed sign of recovery from the valley.

**Trigger:** `current_unit - valley_unit` equals +2.

**Logic:** The system begins to systematically close its profitable short positions and redeploy capital back into long positions.

| Units from Valley | Action | Trading Pattern |
|-------------------|--------|-----------------|
| +2 to +5 | For each unit increase:<br>• Close `hedge_fragment` ETH of short positions<br>• Use proceeds to buy `hedge_fragment` USD long<br>• Buy additional `position_fragment_usd` long with cash reserves | ETH close shorts, USD buy longs |
| +6 | • Close all remaining short positions<br>• Use all proceeds from short closure to buy long<br>• Buy additional `position_fragment_usd` long with cash reserves<br>• Trigger RESET mechanism | Complete conversion to 100% long |

**Key Mechanics:**
- Hedge fragment is calculated from current short position value (including profits), not original value
- Short profits compound into larger recovery purchases
- Each recovery unit purchases more ETH than originally sold due to: (1) short profits providing more USD, and (2) ETH being at a lower price than the peak
- This creates the compound growth effect of the strategy

**Reversals:** If the price falls during this phase, the system reverses the last action, providing a symmetrical response to market fluctuations.

## The RESET Mechanism

The RESET is not a phase but a critical event that re-calibrates the entire strategy, locking in profits (or losses) from the previous cycle and preparing for the next.

**Trigger:** The portfolio becomes 100% long (can occur after completing the RECOVERY phase, or when the RETRACEMENT phase reverses back to fully long without entering DECLINE).

**Process:**
1. All unit-tracking variables are reset: `current_unit = 0`, `peak_unit = 0`, `valley_unit = 0`
2. The `current_notional_allocation` and `current_margin_allocation` are updated to reflect the new total value of the long position. These new values become the baseline for the next cycle
3. Short position tracking is cleared
4. Fragment values are reset to zero (will be recalculated at next peak)
5. The system immediately enters the ADVANCE phase, starting a new cycle from the current market price

**Compound Growth:** This mechanism captures the compound returns by increasing the base position size for the next cycle based on the profits generated during the previous cycle.

## Position Fragment Accounting

The fragment approach ensures optimal capital utilization:

**Starting Position:** 100% long notional value

**RETRACEMENT Phase Distribution:**
- Each retracement unit: 12% of notional value sold from long position, 12% of notional value opened as short position
- ETH amounts sold remain constant (locked at peak), USD amounts for shorts remain constant
- As price drops, same ETH sells for less USD, same USD requires more ETH for shorts

**End Result:** Portfolio holds short position and cash reserves (no long position remaining)

**RECOVERY Phase Compounding:**
- Hedge fragments calculated from profitable short positions (larger than original)
- Recovery purchases use hedge proceeds plus original cash fragments
- Total recovery purchases exceed original position due to short profits
- This creates compound growth in the base position size

**Key Insight:** The short positions generate additional value through price declines, and this value is systematically converted back to long positions during recovery, creating compound growth in the overall position size through complete cycles.