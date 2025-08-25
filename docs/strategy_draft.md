# HyperTrader Strategy Specification

## Overview

This strategy manages multiple cryptocurrency positions using a dynamic allocation system that adjusts between long, short, and cash positions based on price movements. The strategy operates on Hyperliquid with maximum leverage for each coin.

## Position Management

### Core Concepts

- **Position Types**: Each coin can have a long position, short position, and cash position
- **Leverage**: All trades use maximum available leverage for the coin
- **Position Consolidation**: Multiple positions in the same direction are automatically consolidated by Hyperliquid
- **Allocation Split**: Each token has a long allocation and hedge allocation starting at 50/50

### Key Variables

- `initial_position_allocation`: Fixed initial margin amount
- `current_position_allocation`: Dynamic position size that grows over time
- `unit_size`: Dollar amount of price movement the system monitors
- `current_unit`: Current position relative to entry (starts at 0)
- `peak_unit`: Highest unit reached during advance phase
- `valley_unit`: Lowest unit reached during decline phase
- `position_fragment`: 10% of current position value

### Leverage Examples

- **LINK**: $1000 position at 10x leverage = $100 margin
- **XRP**: $1000 position at 20x leverage = $50 margin

## Trading Phases

### 1. Entry Phase

**Initial Setup:**
- Enter with 100% long position
- Set `current_unit = 0`, `peak_unit = 0`, `valley_unit = 0`
- Establish WebSocket connection to Hyperliquid for real-time price data
- Calculate initial `position_fragment` (10% of position value)

### 2. Advance Phase

**Trigger:** Price increases by one `unit_size`

**Actions:**
- Increment `current_unit += 1`
- Increment `peak_unit += 1`
- Recalculate `position_fragment`
- Continue tracking upward movement

### 3. Retracement Phase

**Trigger:** Price decreases by one `unit_size` from advance phase

**Unit Tracking:**
- Decrement `current_unit -= 1`
- Decrement `valley_unit -= 1`

**Retracement Actions:**

| Unit Difference (`current_unit - peak_unit`) | Actions |
|---|---|
| **-1** | • Sell 1 `position_fragment` <br> • Short 1 `position_fragment` |
| **-2** | • Sell 2 `position_fragment` <br> • Short 1 `position_fragment` <br> • Remaining fragment stays in cash |
| **-3** | • Sell 2 `position_fragment` <br> • Short 1 `position_fragment` <br> • Remaining fragment stays in cash |
| **-4** | • Sell 2 `position_fragment` <br> • Short 1 `position_fragment` <br> • Remaining fragment stays in cash |
| **-5** | • Sell remaining long position <br> • Save amount as `temp_cash_fragment` |

**Recovery Actions (Price Moving Up):**

| Unit Change | Actions |
|---|---|
| **-6 → -5** | • Buy long `temp_cash_fragment` |
| **-5 → -4** | • Close short by 1 `position_fragment` <br> • Buy long 2 `position_fragment` |
| **-4 → -3** | • Close short by 1 `position_fragment` <br> • Buy long 2 `position_fragment` |
| **-3 → -2** | • Close short by 1 `position_fragment` <br> • Buy long 2 `position_fragment` |
| **-2 → -1** | • Close remaining short (save as `temp_cash_fragment`) <br> • Buy long `temp_cash_fragment` |

### 4. Decline Phase

**Trigger:** `current_unit - valley_unit = 0` (after reaching unit -7)

**Position State:** 50% short, 50% cash

**Actions:**
- Monitor short position profits
- When `current_unit - valley_unit = 1`:
  - Calculate `hedge_fragment = short_position_value / 4`
  - Recalculate if returning to this level

### 5. Recovery Phase

**Trigger:** `current_unit - valley_unit = 2`

**Unit 2-4 Actions:**
- Close 1 `hedge_fragment` value of short
- Buy 1 `hedge_fragment` value long
- Buy 1 `position_fragment` value long

**Unit 5 Actions:**
- Close remaining short (save as `temp_hedge_value`)
- Buy `temp_hedge_value` long
- Buy 1 `position_fragment` long

**Unit 6:**
- Trigger Reset Phase

### 6. Reset Phase

**Conditions:** Fully long position, no short or cash positions

**Actions:**
- Reset all unit variables to 0
- Update `current_position_allocation` to current margin
- Return to Advance Phase

## Risk Management

- Position fragmentation limits exposure during retracements
- Short positions provide hedging during price declines
- Cash positions preserve capital during volatile periods
- Dynamic allocation adjusts to market conditions

## Expected Outcomes

- Minor value loss during retracement and recovery phases is acceptable
- Short positions during decline phases should increase overall position size
- Strategy aims for net positive returns through complete cycles
