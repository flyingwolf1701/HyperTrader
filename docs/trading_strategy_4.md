# Advanced Hedging Strategy v3.0 - Complete Implementation Guide

## **Core Philosophy**

This is a **bull market thesis strategy** designed to profit in both directions while maintaining long-term upward bias. The system uses automated execution to capture gains during retracements and amplify returns during recoveries, remaining profitable even during significant drawdowns.

The strategy features an **adaptive reset mechanism** that scales with portfolio growth and uses **WebSocket-driven price monitoring** with **CCXT exchange integration** for real-time execution.

---

## **Portfolio Architecture**

### **Two-Bucket System**

* **50% Long Allocation**: Patient money that waits for optimal entries with 2-unit confirmation delays
* **50% Hedge Allocation**: Active trading money that scales in/out based on market movements

### **Unit-Based Calculation System**

* **Unit Definition**: A "unit" equals the dollar value of a 5% gain on the original margin invested  
* **Example**: $100 margin at 10x leverage → 5% gain on margin = $5 → 1 unit = $5 in value  
* **Margin-Based Calculation**: Units calculated from actual cash invested (margin), not leveraged position size
* **Leverage Integration**: Higher leverage creates faster trigger hits, but unit value based on margin
* **Adaptive Scaling**: Unit values recalculate with portfolio growth through reset mechanism

---

## **Database Schema**

### **Core Tables**

#### `trading_plans`
```sql
CREATE TABLE trading_plans (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    margin_amount DECIMAL(15,2) NOT NULL,
    leverage INTEGER DEFAULT 1,
    unit_value DECIMAL(15,2) NOT NULL, -- margin * 0.05
    entry_price DECIMAL(15,8), -- Initial entry price
    peak_price DECIMAL(15,8), -- Current peak (starts at entry_price, unit 0)
    valley_price DECIMAL(15,8), -- Current valley (starts at entry_price, unit 0)
    current_phase VARCHAR(20) DEFAULT 'advance', -- advance, retracement, decline, recovery
    reset_count INTEGER DEFAULT 0, -- Number of system resets
    last_reset_at TIMESTAMP, -- When last reset occurred
    is_active BOOLEAN DEFAULT true,
    auto_execute BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `positions`
```sql
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    trading_plan_id INTEGER REFERENCES trading_plans(id),
    allocation_type VARCHAR(10) NOT NULL, -- 'long', 'hedge'
    position_type VARCHAR(10) NOT NULL, -- 'long', 'short', 'cash'
    percentage DECIMAL(5,2) NOT NULL, -- 0-100
    size DECIMAL(15,8),
    entry_price DECIMAL(15,8),
    current_price DECIMAL(15,8),
    unrealized_pnl DECIMAL(15,2),
    status VARCHAR(20) DEFAULT 'open',
    opened_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `trades`
```sql
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    trading_plan_id INTEGER REFERENCES trading_plans(id),
    order_id VARCHAR(50), -- Exchange order ID
    allocation_type VARCHAR(10) NOT NULL,
    action VARCHAR(20) NOT NULL, -- buy, sell, short, cover
    symbol VARCHAR(20) NOT NULL,
    size DECIMAL(15,8) NOT NULL,
    price DECIMAL(15,8) NOT NULL,
    percentage DECIMAL(5,2), -- Percentage of allocation traded
    fees DECIMAL(15,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    exchange_data JSONB, -- Raw CCXT response
    executed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### `allocation_changes`
```sql
CREATE TABLE allocation_changes (
    id SERIAL PRIMARY KEY,
    trading_plan_id INTEGER REFERENCES trading_plans(id),
    allocation_type VARCHAR(10) NOT NULL,
    old_long_pct DECIMAL(5,2),
    new_long_pct DECIMAL(5,2),
    old_short_pct DECIMAL(5,2),
    new_short_pct DECIMAL(5,2),
    old_cash_pct DECIMAL(5,2),
    new_cash_pct DECIMAL(5,2),
    trigger_price DECIMAL(15,8),
    trigger_units DECIMAL(10,2),
    phase INTEGER,
    reason VARCHAR(100),
    is_reset_event BOOLEAN DEFAULT false, -- System reset trigger
    reset_details JSONB, -- Reset metadata
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## **Position Scaling Matrix**

### **Initial Entry**

* **Both Allocations**: 100% long positions  
* **Total Investment**: $200 (fully deployed)  
* **Peak/Valley Tracking**: Both set to entry price (unit 0 reference)

### **Downward Movement (From Peak)**

| Units Down | Long Allocation | Action Long | Hedge Long | Hedge Short | Action Hedge | Phase | Notes |
|------------|-----------------|-------------|------------|-------------|--------------|-------|-------|
| 0 (Peak) | 100% Long | Hold | 100% Long | 0% | Hold | ADVANCE | Both allocations invested |
| -1 unit | **100% Long** | **WAIT** | 75% Long | 25% Short | Sell 25% → Short | RETRACEMENT | **Long needs 2-unit confirmation** |
| -2 units | **75% Long** | **Sell 25%** | 50% Long | 50% Short | Sell 25% → Short | RETRACEMENT | **CONFIRMED**: Long exits 25% |
| -3 units | **50% Long** | **Sell 25%** | 25% Long | 75% Short | Sell 25% → Short | RETRACEMENT | Long exits another 25% |
| -4 units | **25% Long** | **Sell 25%** | 0% Long | 100% Short | Sell 25% → Short | RETRACEMENT | Long exits another 25% |
| -5 units | **0% Long (Cash)** | **Sell 25%** | 0% Long | 100% Short | Hold Short | DECLINE | Long exits final 25% |

### **Upward Recovery (From Valley)**

| Units Up | Long Allocation | Action Long | Hedge Long | Hedge Short | Action Hedge | Phase | Notes |
|----------|-----------------|-------------|------------|-------------|--------------|-------|-------|
| 0 (Valley) | 0% Long (Cash) | Hold Cash | 0% Long | 100% Short | Hold Short | DECLINE | Valley established |
| +1 unit | **0% Long** | **WAIT** | 25% Long | 75% Short | Cover 25% → Long | RECOVERY | **Need 2-unit confirmation** |
| +2 units | **25% Long** | **Buy 25%** | 50% Long | 50% Short | Cover 25% → Long | RECOVERY | **CONFIRMED**: Buy 25% long |
| +3 units | **50% Long** | **Buy 25%** | 75% Long | 25% Short | Cover 25% → Long | RECOVERY | Buy another 25% long |
| +4 units | **75% Long** | **Buy 25%** | 100% Long | 0% Short | Cover 25% → Long | RECOVERY | Buy another 25% long |
| +5 units | **100% Long** | **Buy 25%** | 100% Long | 0% Short | Hold Long | ADVANCE | Buy final 25% → **RESET TRIGGER** |

---

## **Complete Phase Structure**

### **Phase Overview**

* **ADVANCE**: Building new peaks (both allocations 100% long)
* **RETRACEMENT**: Any decline from peak (confirmation required, hedge starts scaling)
* **DECLINE**: Fully cashed long + shorting (long allocation cashed, shorts compound)
* **RECOVERY**: Any recovery from valley (valley reset, recovery begins)

### **Critical Phase Transitions**

#### **Choppy Trading Detection**
**Trigger**: When long allocation is partially cashed (0% < long_allocation < 100%)

**Automatic Tight Trading Rules**:
* **1-unit movements trigger 25% position changes** (no confirmation delays)
* **0.5 unit moves ignored** to reduce overtrading and fee drag
* **Fast response** when positions need protection
* **Applies to both RETRACEMENT and RECOVERY phases**

---

## **System Reset Mechanism**

### **Reset Trigger Conditions**
The system automatically resets when **both allocations reach 100% long**:
- **Long Allocation**: 100% long / 0% cash  
- **Hedge Allocation**: 100% long / 0% short

### **Reset Process**
```
Price Movement → Both Allocations 100% Long
           ↓
checkFullLongReset() detects reset condition
           ↓
resetSystemToPhase1() executes:
  • peak_price = current_price (new unit 0)
  • valley_price = current_price (new unit 0)  
  • margin_amount = current_portfolio_value
  • unit_value = new_margin * 0.05
  • current_phase = 'advance'
  • reset_count += 1
           ↓
System continues with fresh reference points
```

### **Reset Benefits**
1. **Adaptive Unit Sizing**: Units scale with portfolio growth
2. **Fresh Reference Points**: Eliminates stale peak/valley anchoring
3. **Compounding Growth**: Captures portfolio gains as new margin
4. **Phase Clarity**: Clean return to Phase 1 bull market state

### **Reset Examples**

#### **Recovery Reset**
- **Before**: $100 margin, $5 units, peak $130, current $135
- **Portfolio Value**: $140 (after growth)
- **After Reset**: $140 margin, $7 units, peak/valley $135, phase 'advance'

#### **Continuous Growth Reset**  
- **Before**: $100 margin, never retraced, current $145
- **Portfolio Value**: $145 (continuous growth)
- **After Reset**: $145 margin, $7.25 units, peak/valley $145, phase 'advance'

---

## **CCXT Exchange Integration**

### **Core Functions**

#### **Phase Detection**
* **Unit Calculation**: `calculateUnitsFromReference()` converts price to units
* **Phase Logic**: `determinePhase()` identifies current market state
```python
class TradingPhase(str, Enum):
    ADVANCE = "advance"         # Building new peaks
    RETRACEMENT = "retracement" # Any decline from peak  
    DECLINE = "decline"         # Fully cashed long + shorting
    RECOVERY = "recovery"       # Any recovery from valley
```

#### **Trade Execution**
* **Order Placement**: `placeOrder()` → `exchange.createOrder()` (CCXT)
* **Position Sync**: `getPositions()` → `exchange.fetchPositions()` (CCXT)
* **Balance Check**: `getBalance()` → `exchange.fetchBalance()` (CCXT)
* **Order Cancel**: `cancelOrder()` → `exchange.cancelOrder()` (CCXT)

#### **Trading Rules by Phase**
```python
def get_trading_rules(phase: TradingPhase, long_allocation_pct: float):
    """Dynamic trading rules based on phase and allocation state"""
    
    if phase == TradingPhase.ADVANCE:
        return track_peak_and_hold()
        
    elif phase in [TradingPhase.RETRACEMENT, TradingPhase.RECOVERY]:
        if 0 < long_allocation_pct < 100:  # Partially cashed = choppy
            return TightTradingRules()  # 1-unit triggers, no confirmation
        else:
            return StandardRules()      # 2-unit confirmation required
            
    elif phase == TradingPhase.DECLINE:
        return continue_shorting()
```

### **HyperLiquid Specifics**
* **Exchange Type**: Decentralized Exchange (DEX)
* **Authentication**: Wallet-based signing (not API keys)
* **Order Types**: Limit orders primary, market orders via 5% slippage
* **Rate Limiting**: Built-in CCXT rate limiting and backoff

---

## **Automated Execution Framework**

### **Real-Time Processing Flow**
```
WebSocket Price Update
         ↓
handlePriceUpdate(symbol, newPrice)
         ↓
calculateUnitsFromReference(currentPrice, referencePrice, unitValue)
         ↓
determinePhase(unitsFromPeak, unitsFromValley, currentAllocations)
         ↓
executePhaseActions(tradingPlanId, newPhase, unitsFromReference)
         ↓
executeAllocationChange(tradingPlanId, newAllocations, currentPrice)
         ↓
CCXT Exchange Operations + checkFullLongReset()
```

### **Order Execution Strategy**

#### **Confirmation Rules**
* **Long Allocation**: Always requires 2-unit confirmation before scaling
* **Hedge Allocation**: Immediate response to 1-unit movements
* **Choppy Conditions**: Both allocations use 1-unit triggers (phases 2.5, 4.5)

#### **Trade Validation**
* **Position Limits**: Maximum position size and leverage controls
* **Balance Checks**: Ensure sufficient funds before order placement
* **Risk Management**: Portfolio-level risk limits and emergency stops

---

## **Risk Management & Market Conditions**

### **Automated Choppy Market Handling**

* **Automatic Detection**: Choppy conditions detected by partial allocation state
* **No Manual Intervention**: System handles chop through allocation-based rules
* **Dynamic Response**: Rules change based on current position, not arbitrary phases  
* **Cost-Benefit Trade-off**: Accept small trading costs to prevent major losses

### **Gap Risk Management**

* **Missed Levels**: System picks up at current position, no catch-up trades
* **Recalculation**: Instant adjustment to new reality via `handleGapEvent()`
* **Portfolio Sync**: Align database positions with exchange reality

### **Emergency Controls**

* **Manual Override**: Instant halt of all automated trading
* **Risk Limits**: Maximum drawdown and position size enforcement
* **System Health**: Continuous monitoring of API connectivity and execution

---

## **Performance Tracking & Analytics**

### **Real-Time Metrics**
* **Portfolio Value**: `calculatePortfolioValue()` with unrealized P&L
* **Phase Tracking**: Current phase and transition history
* **Unit Distance**: Real-time units from peak/valley
* **Reset Statistics**: Reset frequency and portfolio growth tracking

### **Trade Analytics**
* **Round Trip P&L**: Complete trade cycle profit/loss calculation
* **Fee Analysis**: Trading cost impact on strategy performance
* **Allocation Efficiency**: Optimal allocation change timing analysis

### **System Performance**
* **Execution Speed**: Order placement and fill time monitoring
* **API Reliability**: CCXT connection health and error rates
* **Database Performance**: Query optimization and data integrity

---

## **User Controls & Monitoring**

### **Manual Overrides**

* **Emergency Stop**: Instant halt of all automated trading
* **Thesis Change**: Pause system for market condition adjustments
* **Leverage Adjustment**: Modify risk multiplier in real-time
* **Reset Override**: Manual system reset capability

### **Monitoring Dashboard**

* **Current Phase**: Which of the 4 phases (advance/retracement/decline/recovery) system is in
* **Current Units**: Distance from peak/valley in unit terms
* **Position Status**: Exact allocation percentages with real-time updates
* **Pending Orders**: Queued trades and trigger levels
* **P&L Tracking**: Real-time profit/loss with projections
* **Reset History**: System reset frequency and growth tracking
* **Chop Detection**: Automatic choppy condition detection based on allocation state

---

## **Mathematical Advantages**

1. **Always Profitable**: Even major crashes generate gains through short positions
2. **Compound Growth**: Successful hedges increase future buying power via reset mechanism
3. **Both Directions**: Profit on the way down AND way up
4. **Automatic Scaling**: Unit values and position sizes scale with portfolio growth
5. **Complete Market Coverage**: 4 phases handle all market conditions
6. **Leverage Amplification**: Higher leverage = faster triggers = more sensitivity
7. **Adaptive Reference Points**: Peak/valley tracking adjusts to market reality

### **Example Performance Through Complete Cycle**

**Starting**: $100 margin, $5 units, 100% long at $100 (ADVANCE)  
**Peak**: Price $130 (+6 units), portfolio $130 (ADVANCE)  
**Retracement**: Price $100 (-6 units), long cashed, shorts profitable (RETRACEMENT/DECLINE)  
**Valley**: Price $70 (-12 units), portfolio $180 (DECLINE - shorts gained $50+)  
**Recovery**: Price $100 (+6 units from valley), both allocations 50% long (RECOVERY)  
**Full Recovery**: Price $130 (+12 units from valley), both 100% long (ADVANCE)  
**Reset**: New margin $200+, new units $10+, fresh cycle begins  

---

## **Implementation Requirements**

### **Technical Stack**
1. **WebSocket Integration**: Real-time price monitoring
2. **CCXT Library**: Exchange abstraction and order management
3. **PostgreSQL**: Robust database for audit trail and state management
4. **Async Python**: Non-blocking execution for real-time responsiveness

### **Security Requirements**
1. **API Wallet Isolation**: Separate trading wallet with limited permissions
2. **Environment Variables**: Secure storage of exchange credentials
3. **Rate Limiting**: Respect exchange limits to avoid penalties
4. **Error Recovery**: Graceful handling of network and exchange errors

### **Monitoring Requirements**
1. **System Health**: API connectivity and database performance
2. **Trade Execution**: Order fill monitoring and slippage tracking
3. **Risk Alerts**: Portfolio limits and emergency condition detection
4. **Performance Analytics**: Strategy effectiveness and optimization metrics

---

## **Core Functions Implementation**

### **1. System Initialization**

#### `initializePosition(symbol, marginAmount, leverageLevel, entryPrice)`
**Purpose**: Set up initial trading plan and allocations  
**Database**: INSERT into `trading_plans`, `positions`  
**CCXT**: None (setup only)

#### `calculateUnitValue(marginAmount, unitPercentage = 5%)`
**Purpose**: Calculate unit size for position scaling  
**Database**: UPDATE `trading_plans.unit_value`  
**Returns**: Unit value in USD

### **2. WebSocket Price Handling**

#### `handlePriceUpdate(symbol, newPrice)`
**Purpose**: Main entry point for all price updates via WebSocket  
**Database**: INSERT into `price_updates`  
**Calls**: `calculateUnitsFromReference()`, `determinePhase()`, `executePhaseActions()`

#### `calculateUnitsFromReference(currentPrice, referencePrice, unitValue)`
**Purpose**: Calculate how many units moved from peak or valley  
**Database**: READ from `trading_plans`  
**Returns**: Number of units (can be negative)

### **3. Phase Management**

#### `determinePhase(unitsFromPeak, unitsFromValley, currentAllocations)`
**Purpose**: Determine current market phase based on price movement  
**Database**: READ `positions`, UPDATE `trading_plans.current_phase`  
**Logic**:
- **ADVANCE**: Building new highs
- **RETRACEMENT**: Decline from peak (need confirmation)  
- **DECLINE**: Continued decline (full cash + short)
- **RECOVERY**: Recovery from valley (need confirmation)

#### `executePhaseActions(tradingPlanId, newPhase, unitsFromReference, currentPrice)`
**Purpose**: Execute appropriate trades for phase transition  
**Database**: READ `positions`, CALL trade execution functions  
**CCXT**: Via `executeAllocationChange()`

### **4. Position Management**

#### `getAllocations(tradingPlanId)`
**Purpose**: Get current allocation percentages for long and hedge buckets  
**Database**: SELECT from `positions` WHERE `trading_plan_id`  
**Returns**: `{long: {long_pct, cash_pct}, hedge: {long_pct, short_pct}}`

#### `calculateTargetAllocation(phase, unitsFromReference, confirmationStatus)`
**Purpose**: Determine target allocations for current market conditions  
**Database**: None (pure calculation)  
**Returns**: Target allocation percentages

#### `executeAllocationChange(tradingPlanId, newAllocations, currentPrice)`
**Purpose**: Execute trades to achieve target allocations  
**Database**: INSERT into `trades`, UPDATE `positions`  
**CCXT**: `exchange.createOrder()` for each required trade  
**Calls**: `calculateTradeSize()`, `placeOrder()`, `checkFullLongReset()`  
**Post-Execute**: Always checks if system should reset after allocation change

### **5. CCXT Integration Functions**

#### `placeOrder(symbol, side, amount, orderType='market', price=null)`
**Purpose**: Place order via CCXT  
**CCXT**: `exchange.createOrder(symbol, type, side, amount, price)`  
**Database**: INSERT into `trades` with `status='pending'`  
**Returns**: Exchange order ID

#### `cancelOrder(orderId, symbol)`
**Purpose**: Cancel pending order  
**CCXT**: `exchange.cancelOrder(orderId, symbol)`  
**Database**: UPDATE `trades` SET `status='cancelled'`

#### `getPositions()`
**Purpose**: Fetch current positions from exchange  
**CCXT**: `exchange.fetchPositions()`  
**Database**: Compare with local `positions` table, sync if needed

#### `getBalance()`
**Purpose**: Get account balance  
**CCXT**: `exchange.fetchBalance()`  
**Returns**: Available cash and positions

### **6. Trade Execution Support**

#### `calculateTradeSize(currentSize, currentPercent, targetPercent, totalValue)`
**Purpose**: Calculate exact trade size needed for allocation change  
**Database**: None (pure calculation)  
**Returns**: Trade size in base currency

#### `validateTrade(symbol, side, amount, availableBalance)`
**Purpose**: Ensure trade is valid before execution  
**Database**: READ current `positions`  
**Returns**: Boolean validation result

#### `trackTradeExecution(tradeId, exchangeOrderId, status, executedPrice)`
**Purpose**: Update trade status from exchange callbacks  
**Database**: UPDATE `trades` with execution details  
**CCXT**: Called from order status webhooks/polling

### **7. Reference Point Management**

#### `updatePeakTracking(newPeakPrice, tradingPlanId)`
**Purpose**: Update peak price when new highs are reached (moving up from unit 0)  
**Database**: UPDATE `trading_plans.peak_price`  
**Logic**: Only updates if new price is higher than current peak

#### `updateValleyTracking(newValleyPrice, tradingPlanId)`
**Purpose**: Update valley price when new lows are reached (moving down from unit 0)  
**Database**: UPDATE `trading_plans.valley_price`  
**Logic**: Only updates if new price is lower than current valley

#### `checkFullLongReset(tradingPlanId)`
**Purpose**: Detect when both allocations are 100% long and trigger system reset  
**Database**: READ `positions` to check if long=100%, hedge=100% long  
**Calls**: `resetSystemToPhase1()` if conditions met  
**Trigger**: Called after every allocation change

#### `resetSystemToPhase1(tradingPlanId, currentPrice, newMarginAmount)`
**Purpose**: Complete system reset when back to full long position  
**Database**: 
- UPDATE `trading_plans` SET `peak_price = currentPrice`, `valley_price = currentPrice`
- UPDATE `trading_plans` SET `current_phase = 'advance'`, `margin_amount = newMarginAmount`
- RECALCULATE `unit_value = newMarginAmount * 0.05`
- INSERT new record in `allocation_changes` noting reset event

**Logic**: 
- Sets peak and valley to current price (unit 0 reference)
- Recalculates unit size based on new margin amount
- Resets phase to 'advance' (fresh start)
- Logs reset event for audit trail

### **8. Special Scenario Handling**

#### `handleChoppyConditions(tradingPlanId, priceHistory)`
**Purpose**: Detect and handle sideways/choppy market conditions  
**Database**: READ recent `price_updates`  
**Logic**: Activates tighter trading rules when partially allocated

#### `handleGapEvent(tradingPlanId, previousPrice, currentPrice)`
**Purpose**: Handle overnight gaps or missing price data  
**Database**: UPDATE `trading_plans` to current reality  
**Logic**: Don't chase missed trades, adjust to current position

#### `handleExtremeVolatility(tradingPlanId, priceSwings, timeWindow)`
**Purpose**: Manage rapid price oscillations  
**Database**: Log volatility events  
**Logic**: May pause trading or use wider tolerances

### **9. Performance Tracking**

#### `calculatePortfolioValue(tradingPlanId, currentPrice)`
**Purpose**: Calculate total portfolio value  
**Database**: READ all `positions` for trading plan  
**Returns**: Total value including unrealized P&L

#### `updateUnrealizedPnL(tradingPlanId, currentPrice)`
**Purpose**: Update unrealized P&L for all positions  
**Database**: UPDATE `positions.unrealized_pnl`  
**Called**: On every price update

#### `calculateRoundTripPnL(entryTrades, exitTrades, fees)`
**Purpose**: Calculate completed round-trip profit/loss  
**Database**: READ related `trades`  
**Returns**: Net P&L after fees

---

## **Consolidated Function Groups**

### **WebSocket Price Handler (Single Entry Point)**
- `handlePriceUpdate()` → Processes all incoming price data
- `calculateUnitsFromReference()` → Converts price to units
- `determinePhase()` → Identifies current market phase
- `executePhaseActions()` → Triggers appropriate trades

### **Position Management (State Tracking)**
- `getAllocations()` → Current allocation state
- `calculateTargetAllocation()` → Desired allocation state  
- `executeAllocationChange()` → Bridge current to target state

### **Exchange Integration (CCXT Wrappers)**
- `placeOrder()` → Generic order placement
- `cancelOrder()` → Order cancellation
- `getPositions()` → Position synchronization
- `getBalance()` → Account balance

### **Database Operations (State Persistence)**
- All functions read/write appropriate tables
- No duplicate data storage
- Clean separation of concerns

---