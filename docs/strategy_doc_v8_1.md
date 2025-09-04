# Advanced Hedging Strategy v8.1.0 - Dual Wallet Architecture

## Core Philosophy

This is a bull market thesis strategy engineered to capitalize on price movements in both directions while maintaining a long-term upward bias. The system leverages automated execution across **two separate wallets** on the Hyperliquid platform to overcome position netting constraints and achieve true portfolio diversification. The strategy systematically takes profits during price retracements and compounds returns during recoveries through coordinated dual-wallet operations.

The strategy is centered around a dynamic four-phase system (Advance, Retracement, Decline, Recovery) with a crucial reset mechanism that re-calibrates both wallets after a full cycle, allowing profits to compound into the new base capital.

## Dual-Wallet Architecture

### Position Netting Challenge

**The Fundamental Constraint**: On Hyperliquid (and most exchanges), you cannot hold both long and short positions simultaneously in the same asset on a single wallet. When attempting to "open" a short position while holding a long position, the positions automatically net against each other, reducing the long position instead of creating separate hedging positions.

**The Solution**: **Dual-Wallet Architecture** - Split execution across two separate wallets with distinct strategic roles to achieve true portfolio diversification.

### Wallet Allocation and Roles

**Long Wallet (50% of total allocation)**:
- **Purpose**: Execute retracement scaling strategy with gradual position management
- **Initial Allocation**: 50% of desired total position size
- **Strategy Focus**: Partial position scaling with cash reserve accumulation
- **Risk Profile**: Conservative scaling that fully exits to cash by decline phase

**Hedge Wallet (50% of total allocation)**:
- **Purpose**: Provide aggressive counter-movement positioning through complete position rotation
- **Initial Allocation**: 50% of desired total position size  
- **Strategy Focus**: Full position rotation from long to short during retracements
- **Risk Profile**: Maximum exposure to directional moves through complete position changes

### Portfolio Composition Across Phases

**ADVANCE Phase (Both wallets aligned)**:
- Long Wallet: 100% long position
- Hedge Wallet: 100% long position (mirrors long strategy)
- **Total Portfolio**: 100% long (distributed across two wallets)

**RETRACEMENT Phase (Diversification through rotation)**:
- Long Wallet: Gradually reducing long positions (fragment-based scaling)
- Hedge Wallet: Complete long exit → Progressive short position building
- **Total Portfolio**: Long wallet (partial long + cash) + Hedge wallet (cash → shorts)

**DECLINE Phase (Defensive positioning)**:
- Long Wallet: Cash reserves from scaled positions
- Hedge Wallet: Accumulated short positions profiting from continued decline
- **Total Portfolio**: Long wallet (cash) + Hedge wallet (shorts)

**RECOVERY Phase (Coordinated rebuilding)**:
- Long Wallet: Rebuilding long positions from cash reserves using fragment scaling
- Hedge Wallet: Scale out of shorts over 4 units, then complete rotation to 100% long
- **Total Portfolio**: Long wallet (cash → long via scaling) + Hedge wallet (shorts → cash → all-in long)

## Key Variables

- `unit_size`: The trader-defined price movement that constitutes one unit
- `entry_price`: The average entry price of positions, calculated per wallet
- `current_unit`: The current price distance from entry_price, measured in units
- `peak_unit`: The highest unit reached during an ADVANCE phase
- `valley_unit`: The lowest unit reached during a DECLINE phase
- `position_map`: Data structure mapping unit levels to fragments, orders, and execution data

## Trading Pattern: Coordinated Dual-Wallet Execution

**Core Principle**: Each unit level executes exactly **one fragment** of the appropriate type - no multipliers or scaling factors.

**Trading Pattern**:
- **Buy Operations**: Use USD fragment amounts (easier to calculate from cash position and deploy larger amounts)
- **Sell Operations**: Use asset fragment amounts for consistent scaling regardless of price

The strategy employs coordinated execution across both wallets with distinct trading patterns:

**Long Wallet Pattern (Fragment-Based):**
- **Position Building**: USD fragment amounts (easier cash deployment and larger position sizing)
- **Position Scaling**: Asset fragment amounts for consistent execution regardless of price
- **Order Management**: Trailing limit orders using pre-calculated fragment values

**Hedge Wallet Pattern (Rotational):**
- **Long Phase**: USD fragment amounts matching long wallet timing
- **Rotation Trigger**: Complete long exit using total position value
- **Short Phase**: USD fragment amounts for consistent notional exposure  
- **Recovery Rotation**: Asset fragment amounts for short exits → USD fragment amounts for long rebuilding

## Pre-Placed Limit Order Architecture

### Core Execution Philosophy

**Passive Order Management**: Instead of actively placing market orders in response to price movements, the strategy pre-places limit orders at calculated price levels and manages the order ladder dynamically.

**Benefits**:
- **Zero Execution Lag**: Orders execute instantly when price levels are hit
- **Network Resilience**: Orders function even if WebSocket connection drops
- **Reduced Slippage**: Limit orders execute at predetermined prices
- **Lower Exchange Fees**: Limit orders typically have lower fees than market orders
- **System Reliability**: Less dependent on real-time system responsiveness

### Order Ladder Management

**Sliding Window Approach**: Each wallet maintains a sliding window of 4 active limit orders that trail the current price position.

**Initial Setup** (at position entry):
```
Current Price: $4500 (Unit 0)
Place limit orders at:
- Unit -1: $4475 (sell 1 fragment)
- Unit -2: $4450 (sell 1 fragment)  
- Unit -3: $4425 (sell 1 fragment)
- Unit -4: $4400 (sell 1 fragment)
```

**Dynamic Adjustment** (as price advances):
- **New Peak Reached**: Place new limit order at previous peak level
- **Remove Furthest**: Cancel the limit order furthest from current price
- **Maintain Window**: Always keep exactly 4 active orders trailing price

**Example Progression**:
- **Unit +1 Reached**: Place limit at Unit 0, cancel limit at Unit -4
- **Unit +2 Reached**: Place limit at Unit +1, cancel limit at Unit -3
- **Active Orders**: Always maintain [current-1, current-2, current-3, current-4]

### Order Management Data Structure

Each unit level maintains complete execution information in a unified structure:

```python
unit_orders = {
    unit_level: {
        "order_id": null,                    # Active order ID (null if inactive)
        "type": null,                        # Order type (null if inactive)
        "price": calculated_price,           # Execution price for this unit
        "long_fragment_usd": fragment_value, # USD amount for long entries
        "long_fragment_asset": asset_amount, # Asset amount for long exits
        "short_fragment_usd": fragment_value,# USD amount for short entries  
        "short_fragment_asset": asset_amount # Asset amount for short exits
    }
}
```

**Fragment Calculation**: All fragments represent 25% of the wallet's position value, calculated at peak price and locked for the entire cycle.

### Order Execution Flow

**Automatic Execution**:
1. **Limit Hit**: Exchange executes order automatically at predetermined price
2. **System Notification**: Bot receives fill notification via WebSocket
3. **Order Update**: Mark executed order as filled in position_map structure
4. **Ladder Maintenance**: Add new trailing order if peak has advanced
5. **Fragment Deployment**: Use pre-calculated fragment amounts for execution

**No Real-Time Decisions**: The system doesn't make trading decisions in real-time - all decisions are pre-encoded in the limit order placement strategy.

## The Four-Phase Trading System

### 1. ADVANCE Phase

**Condition**: Both wallets hold 100% long positions

**Long Wallet Actions:**
- Track price increases by unit increments
- Calculate and lock fragments at new peaks (25% of position value)
- Place trailing limit orders using locked fragment values
- Maintain 4-order sliding window for automatic execution

**Hedge Wallet Actions:**
- Mirror long wallet's advance tracking
- Prepare for complete position rotation at retracement trigger
- Calculate matching fragment values for coordinated execution
- Maintain independent trailing order management

**Coordination**: Both wallets move in unison during advance phase, doubling effective long exposure across the combined portfolio.

### 2. RETRACEMENT Phase

This phase triggers when price drops one unit from the established peak, with **fundamentally different execution per wallet**.

**Long Wallet Logic (One Fragment Per Unit):**
| Units from Peak | Action | Pattern |
|-----------------|--------|---------|
| -1 | Sell 1 fragment of asset | Asset-based execution |
| -2 | Sell 1 fragment of asset | Asset-based execution |
| -3 | Sell 1 fragment of asset | Asset-based execution |
| -4 | Sell 1 fragment of asset | Complete position exit |

**Hedge Wallet Logic (One Fragment Per Unit):**
| Units from Peak | Action | Pattern |
|-----------------|--------|---------|
| -1 | **Complete long exit** → Short 1 fragment USD | Full rotation |
| -2 | Short 1 fragment USD | USD-based short entry |
| -3 | Short 1 fragment USD | USD-based short entry |
| -4 | Short 1 fragment USD | Maximum short exposure |

**Key Difference**: The hedge wallet performs **complete position rotation** rather than gradual scaling, providing true directional hedging for the portfolio.

**Reversals**: If price moves back up during retracement:
- Long wallet: Reverse last scaling action (re-buy sold portions using cash)
- Hedge wallet: Must go through cash - cannot directly adjust between position types

### 3. DECLINE Phase

**Long Wallet**: 
- Hold cash reserves from position scaling
- **No long exposure** (fully scaled out during retracement)
- Prepare cash for recovery purchases

**Hedge Wallet**:
- Hold accumulated short positions
- Profit from continued price decline
- Track valley formation for recovery timing

**Portfolio Status**: Long wallet (cash) + Hedge wallet (shorts) = True portfolio diversification.

### 4. RECOVERY Phase

**Trigger**: Price recovers +2 units from valley

This phase triggers when price rises two units from the established valley, with **coordinated rebuilding across both wallets**.

**Long Wallet Actions**:
- Deploy cash reserves to rebuild long positions
- Use fragment-based sizing (USD-based purchases)
- Scale back into full long exposure

**Long Wallet Logic (One Fragment Per Unit):**
| Units from Valley | Action | Pattern |
|------------------|--------|---------|
| +1 | Buy 1 fragment USD worth | USD-based execution |
| +2 | Buy 1 fragment USD worth | USD-based execution |
| +3 | Buy 1 fragment USD worth | USD-based execution |
| +4 | Buy 1 fragment USD worth | Complete position rebuild |

**Hedge Wallet Actions**:
- Close short positions in fragments (25% of current short value) over 4 stages
- **Complete Rotation**: Once fully exited from shorts, go all-in on long position
- Single large long entry using all available capital (short profits + original capital)

**Hedge Wallet Logic (One Fragment Per Unit):**
| Units from Valley | Action | Pattern |
|------------------|--------|---------|
| +1 | Close 1 fragment of shorts | Asset-based short closure |
| +2 | Close 1 fragment of shorts | Asset-based short closure |
| +3 | Close 1 fragment of shorts | Asset-based short closure |
| +4 | Close remaining shorts → **All-in long** | Complete rotation |

**Key Difference**: The long wallet performs **gradual scaling** from cash back to long, while the hedge wallet performs **complete position rotation** from shorts to all-in long.

**Reversals**: If price moves back down during recovery:
- Long wallet: Reverse last scaling action (sell recently bought portions)
- Hedge wallet: Must go through cash - cannot directly adjust between position types

**Coordination**: Both wallets work together using standardized fragments:
- Identical fragment sizing (25% of respective position values)
- Synchronized unit tracking for consistent triggers
- Independent order management with coordinated timing
- Automated execution through trailing limit orders

## The RESET Mechanism

**Trigger**: Both wallets return to 100% long positions after complete cycle

**Process Per Wallet**:
1. Calculate individual wallet performance and profit/loss
2. Update each wallet's baseline allocation based on realized gains
3. Reset unit tracking variables independently
4. Clear position rotation tracking for hedge wallet
5. Re-establish coordinated entry prices for new cycle

**Compound Growth**: Each wallet independently compounds its profits:
- Long wallet: Profits from scaling + cash management
- Hedge wallet: Profits from position rotation + short-side gains
- Combined effect: Accelerated compound growth from dual profit streams

## Risk Management and Coordination

**Leverage Management**:
- Both wallets utilize maximum available leverage (25x for ETH)
- Position sizing coordinated to maintain 50/50 allocation split
- Margin requirements calculated independently per wallet

**Timing Coordination**:
- Phase transitions synchronized across both wallets
- Unit tracking shared between wallets for consistent triggers
- Recovery timing coordinated for maximum compound effect

**Portfolio Monitoring**:
- Combined portfolio composition tracked in real-time
- Individual wallet performance monitored independently
- Overall strategy performance calculated from combined results

### Risk Management Through Limits

**Predetermined Execution**: All trading decisions are made when limits are placed, not when they execute

**Price Protection**: Limit orders ensure execution only at acceptable price levels

**System Independence**: Strategy continues executing even during:
- WebSocket disconnections
- System downtime  
- Network latency issues
- Exchange API delays

**Order Coordination**: Each wallet manages its independent limit order ladder without requiring real-time coordination between wallets

## Expected Performance Benefits

**Enhanced Hedging**: True short exposure during declines (not just reduced long exposure)

**Dual Profit Streams**: 
- Fragment-based scaling profits (long wallet)
- Position rotation profits (hedge wallet)

**Accelerated Compounding**: Two independent profit centers compounding simultaneously

**Improved Risk Management**: Genuine portfolio diversification during volatile periods

**Market Adaptability**: Strategy works effectively in both trending and ranging markets through coordinated wallet operations

## Implementation Considerations

**Technical Requirements**:
- Dual wallet management system
- Pre-placed limit order coordination across wallets
- Real-time order ladder maintenance and adjustment  
- Independent order execution monitoring per wallet
- Automatic order replacement and cancellation system

**Capital Efficiency**:
- 50/50 split maintains desired total exposure
- Leverage utilization maximized across both wallets
- No capital inefficiency from position netting constraints

**Execution Complexity**:
- Increased coordination requirements
- More complex state management
- Enhanced monitoring and reporting needs

## Strategy Evolution: v7.0.3 → v8.1.0

**Key Changes**:
- Single wallet → Dual wallet architecture
- Position netting workaround → True portfolio diversification
- Partial hedging → Complete position rotation capability
- Limited profit streams → Dual profit stream compounding
- Market order execution → Pre-placed limit order management
- Complex fragment multipliers → Simplified one-fragment-per-unit execution

**Maintained Elements**:
- Core four-phase system logic
- Unit-based tracking methodology
- Fragment calculation principles (updated to 25%)
- Reset mechanism for compound growth
- Bull market thesis and directional bias

The Advanced Hedging Strategy v8.1.0 represents a fundamental architectural evolution that overcomes exchange limitations while maintaining the sophisticated market timing and profit compounding capabilities that define this systematic approach.