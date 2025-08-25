Advanced Hedging Strategy v6.0.0
Core Philosophy
This is a bull market thesis strategy engineered to capitalize on price movements in both directions while maintaining a long-term upward bias. The system leverages automated execution on the Hyperliquid platform to systematically take profits during price retracements and compound returns during recoveries. The core logic is designed to remain resilient and profitable even through significant market volatility and drawdowns.

The strategy is centered around a dynamic four-phase system (Advance, Retracement, Decline, Recovery) and a crucial reset mechanism that re-calibrates the system after a full cycle, allowing profits to compound into the new base capital.

Portfolio Architecture
Unified Position Management
For each asset, the strategy manages a single, unified position on Hyperliquid that is comprised of three components: a long position, a short position, and a cash position. The system recognizes that on Hyperliquid, multiple long or short orders for the same coin are consolidated into a single position with an averaged entry price.

Leverage and Allocation
Maximum Leverage: All orders are placed utilizing the maximum leverage available for the specific asset. This means the required margin is a fraction of the notional position size (e.g., a $1,000 position with 20x leverage requires $50 of margin).

Position Allocation:

initial_position_allocation: A fixed dollar amount representing the margin committed at the start of a new trade cycle.

current_position_allocation: The real-time margin value of the position. This value fluctuates as the strategy executes and will ideally grow over time. It is reset to the current margin value during the RESET mechanism.

Unit-Based Tracking System
Unit Definition: A "unit" is a manually defined price movement (e.g., $0.50 for ETH) that serves as the fundamental trigger for all strategic actions. The unit_size gives the trader direct control over the strategy's sensitivity to market volatility.

Execution: Trading actions are only triggered upon the completion of a full unit movement.

Post-MVP Notes: For future versions, the unit_size could become dynamic. It could adjust based on the current trading phase or other market conditions, such as stochastic RSI or trading volume, to make the strategy more adaptive.

Key Variables
unit_size: The trader-defined price movement that constitutes one unit.

entry_price: The average entry price of the position, as calculated and managed by Hyperliquid.

current_unit: The current price distance from the entry_price, measured in units. Initialized at 0.

peak_unit: The highest unit reached during an ADVANCE phase. Initialized at 0 and updated as new highs are made.

valley_unit: The lowest unit reached during a DECLINE phase. Initialized at 0 and updated as new lows are made.

position_fragment: Calculated during the ADVANCE phase as 10% of the current total long position value. This variable defines the size of scaling actions during the RETRACEMENT phase.

hedge_fragment: Calculated during the DECLINE phase as 25% (1/4) of the current total short position value. This variable defines the size of scaling actions during the RECOVERY phase.

The Four-Phase Trading System
1. ADVANCE Phase
This is the initial state upon entering a trade, assuming a bullish outlook.

Condition: The entire position is 100% long.

Actions:

As the price increases by one unit_size, current_unit and peak_unit are both incremented by +1.

The system continuously recalculates position_fragment (10% of the growing position value) to prepare for a potential retracement.

The system remains in the ADVANCE phase as long as the price continues to make new highs (i.e., current_unit continues to increase).

2. RETRACEMENT Phase
This phase is triggered when the price falls from its peak.

Trigger: The price drops one unit from the established peak_unit.

Logic: The system executes a series of pre-defined actions based on the number of units the price has fallen from the peak (current_unit - peak_unit).

Units from Peak

Action

Portfolio State (Approx.)

-1

• Sell 1 position_fragment of the long position.<br>• Open a new short position equal to 1 position_fragment.

80% Long / 10% Short / 10% Cash

-2

• Sell 2 position_fragments of the long position.<br>• Add 1 position_fragment to the short position.

50% Long / 20% Short / 30% Cash

-3

• Sell 2 position_fragments of the long position.<br>• Add 1 position_fragment to the short position.

20% Long / 30% Short / 50% Cash

-4

• Sell 2 position_fragments of the long position.<br>• Add 1 position_fragment to the short position.

0% Long / 40% Short / 60% Cash

-5

• Sell the remaining long position.<br>• Add the value of this final sale to the short position.

0% Long / ~50% Short / ~50% Cash

-6 & below

Enters the DECLINE phase.

Holding Short and Cash

Reversals: If the price moves back up during this phase, the system executes the exact opposite of the last action. For example, moving from -3 units back to -2 units would involve buying back 2 position_fragments long and closing 1 position_fragment of the short position.

3. DECLINE Phase
This phase is triggered after a significant retracement, where the position is now fully defensive and positioned to profit from a continued downtrend.

Trigger: The system has completed the action for -5 units from the peak.

Condition: The portfolio is approximately 50% in a short position and 50% in cash.

Actions:

As the price continues to fall, current_unit is decremented, and valley_unit is updated to match current_unit, tracking the new low.

The system holds the short position, allowing it to accumulate profit.

If the price begins to recover (current_unit increments), the system calculates hedge_fragment (25% of the short position's current value) in preparation for the RECOVERY phase.

4. RECOVERY Phase
This phase is triggered when the price shows a confirmed sign of recovery from the valley.

Trigger: current_unit - valley_unit equals +2.

Logic: The system begins to systematically close its profitable short position and redeploy capital back into a long position.

Units from Valley

Action

+2 to +4

For each unit increase:<br>• Close 1 hedge_fragment of the short position.<br>• Use proceeds to buy 1 hedge_fragment long.<br>• Buy an additional 1 position_fragment long with cash reserves.

+5

• Close the remainder of the short position.<br>• Use all proceeds from the short closure to buy long.<br>• Buy an additional 1 position_fragment long with cash reserves.

+6

The position is now fully long. The system triggers the RESET mechanism and re-enters the ADVANCE phase.

Reversals: If the price falls during this phase, the system reverses the last action, providing a symmetrical response to market fluctuations.

The RESET Mechanism
The RESET is not a phase but a critical event that re-calibrates the entire strategy, locking in profits (or losses) from the previous cycle and preparing for the next.

Trigger: The system's position becomes 100% long (typically after completing the RECOVERY phase).

Process:

All unit-tracking variables are reset: current_unit = 0, peak_unit = 0, valley_unit = 0.

The current_position_allocation is updated to reflect the new total margin value of the fully long position. This new value becomes the baseline for the next cycle.

The system immediately enters the ADVANCE phase, starting a new cycle from the current market price.

Important Mathematical Clarification
Understanding Position Fragment Accounting

The position_fragment approach ensures no double-counting of capital:

Starting Position: 100% long (10 fragments at 10% each)

RETRACEMENT Phase Distribution:
- Units -1 to -4: Total of 8 fragments (80%) are sold from the long position
- Of these proceeds: 4 fragments (40%) go to short positions, 4 fragments (40%) held as cash
- Unit -5: Final 2 fragments (20%) sold and added to short position

End Result: 0% long, 50% short, 50% cash

Key Insight: The shorts are funded BY the sale of longs, not in addition to them. We're redistributing 100% of our position, not creating leverage beyond our initial capital. The 10% fragment size (rather than 12.5% which would be 1/8) provides a buffer to absorb trading losses from price reversals during phase transitions.