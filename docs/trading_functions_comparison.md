# Trading System Functions - Higher Order vs Regular Functions

## Higher-Order Functions (Orchestrators)

These functions coordinate multiple operations and call other functions to accomplish complex workflows.

### `handlePriceUpdate(symbol, newPrice)`
**Description**: Main orchestrator for all real-time price updates via WebSocket connections. Processes incoming price data and coordinates the entire trading decision pipeline from price analysis through trade execution.

**Parameters**: 
- `symbol` (string): Trading symbol receiving price update
- `newPrice` (float): Latest market price

**Functions Called**:
- `calculateUnitsFromReference()`
- `determinePhase()`  
- `executePhaseActions()`
- `updateUnrealizedPnL()`

**CCXT Support**: No - Orchestration function
**MVP Required**: ✅ True

---

### `executePhaseActions(tradingPlanId, newPhase, unitsFromReference, currentPrice)`
**Description**: Orchestrates trade execution for phase transitions. Determines what trades are needed based on the new market phase and coordinates their execution through the allocation management system.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan
- `newPhase` (string): Target market phase
- `unitsFromReference` (integer): Units from peak/valley
- `currentPrice` (float): Current market price

**Functions Called**:
- `getAllocations()`
- `calculateTargetAllocation()`
- `executeAllocationChange()`

**CCXT Support**: Yes - Via called functions
**MVP Required**: ✅ True

---

### `executeAllocationChange(tradingPlanId, newAllocations, currentPrice)`
**Description**: Orchestrates the complex process of changing portfolio allocations. Calculates required trades, validates them, executes through exchange, and manages post-execution checks including system resets.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan
- `newAllocations` (object): Target allocation percentages
- `currentPrice` (float): Current market price for trade execution

**Functions Called**:
- `getAllocations()`
- `calculateTradeSize()`
- `validateTrade()`
- `placeOrder()`
- `trackTradeExecution()`
- `checkFullLongReset()`

**CCXT Support**: Yes - Via placeOrder() calls
**MVP Required**: ✅ True

---

### `initializePosition(symbol, marginAmount, leverageLevel, entryPrice)`
**Description**: Orchestrates the complete setup of a new trading strategy. Creates database records, calculates initial parameters, and establishes the foundation for automated trading.

**Parameters**: 
- `symbol` (string): Trading pair symbol (e.g., "BTC-USD")
- `marginAmount` (float): Initial capital allocation 
- `leverageLevel` (integer): Leverage multiplier (1-10)
- `entryPrice` (float): Current market price for reference

**Functions Called**:
- `calculateUnitValue()`
- Database creation operations

**CCXT Support**: No - Setup orchestration
**MVP Required**: ✅ True

---

### `resetSystemToPhase1(tradingPlanId, currentPrice, newMarginAmount)`
**Description**: Orchestrates complete system reset when profitable cycles complete. Coordinates updating all reference points, recalculating parameters, and logging the reset event.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan
- `currentPrice` (float): Current market price for new reference
- `newMarginAmount` (float): Updated portfolio value as new margin

**Functions Called**:
- `calculateUnitValue()`
- `updatePeakTracking()`
- `updateValleyTracking()`
- Database update operations

**CCXT Support**: No - System reset orchestration
**MVP Required**: ✅ True

---

### `handleGapEvent(tradingPlanId, previousPrice, currentPrice)`
**Description**: Orchestrates gap handling by analyzing the situation and coordinating appropriate adjustments to system state without attempting catch-up trades.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan
- `previousPrice` (float): Last known price before gap
- `currentPrice` (float): Current price after gap

**Functions Called**:
- `calculateUnitsFromReference()`
- `determinePhase()`
- `getAllocations()`

**CCXT Support**: No - Gap analysis orchestration
**MVP Required**: ⭕ False

---

### `generatePerformanceReport(allMetrics, phaseBreakdown, keySuccessFactors)`
**Description**: Orchestrates comprehensive performance analysis by gathering data from multiple sources and generating detailed reports.

**Parameters**: 
- `allMetrics` (object): Complete performance metrics
- `phaseBreakdown` (object): Performance by market phase
- `keySuccessFactors` (array): Identified success factors

**Functions Called**:
- `calculatePortfolioValue()`
- `calculateRoundTripPnL()`
- Various performance calculation functions

**CCXT Support**: No - Reporting orchestration
**MVP Required**: ⭕ False

---

## Regular Functions (Workers)

These functions perform specific tasks and are called by higher-order functions.

### `calculateUnitsFromReference(currentPrice, referencePrice, unitValue)`
**Description**: Calculates how many units the price has moved from a reference point (peak or valley). This converts raw price movements into standardized unit measurements that drive trading decisions.

**Parameters**: 
- `currentPrice` (float): Current market price
- `referencePrice` (float): Peak or valley reference price
- `unitValue` (float): Value of one unit in currency

**Called By**:
- `handlePriceUpdate()`
- `handleGapEvent()`

**CCXT Support**: No - Pure calculation
**MVP Required**: ✅ True

---

### `determinePhase(unitsFromPeak, unitsFromValley, currentAllocations)`
**Description**: Determines current market phase based on price movement and allocation state. Returns one of four phases: ADVANCE, RETRACEMENT, DECLINE, or RECOVERY.

**Parameters**: 
- `unitsFromPeak` (integer): Units moved from peak price
- `unitsFromValley` (integer): Units moved from valley price  
- `currentAllocations` (object): Current allocation percentages

**Called By**:
- `handlePriceUpdate()`
- `handleGapEvent()`

**CCXT Support**: No - Phase logic
**MVP Required**: ✅ True

---

### `calculateTargetAllocation(phase, unitsFromReference, confirmationStatus)`
**Description**: Determines target allocation percentages for current market conditions. Pure calculation function that returns desired allocation state without executing trades.

**Parameters**: 
- `phase` (string): Current market phase
- `unitsFromReference` (integer): Units from peak/valley
- `confirmationStatus` (boolean): Whether confirmation criteria are met

**Called By**:
- `executePhaseActions()`

**CCXT Support**: No - Pure calculation
**MVP Required**: ✅ True

---

### `getAllocations(tradingPlanId)`
**Description**: Retrieves current allocation percentages for both long and hedge buckets from the database. Returns current position state for decision making.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan

**Called By**:
- `executePhaseActions()`
- `executeAllocationChange()`
- `handleGapEvent()`

**CCXT Support**: No - Database query
**MVP Required**: ✅ True

---

### `calculateTradeSize(currentSize, currentPercent, targetPercent, totalValue)`
**Description**: Calculates exact trade size needed to move from current to target allocation percentage. Ensures precise position sizing without over or under-trading.

**Parameters**: 
- `currentSize` (float): Current position size
- `currentPercent` (float): Current allocation percentage
- `targetPercent` (float): Target allocation percentage  
- `totalValue` (float): Total portfolio value

**Called By**:
- `executeAllocationChange()`

**CCXT Support**: No - Pure calculation
**MVP Required**: ✅ True

---

### `calculateUnitValue(marginAmount, unitPercentage = 5%)`
**Description**: Calculates unit size for position scaling based on margin amount. Each unit represents standardized position sizing that scales with portfolio growth.

**Parameters**: 
- `marginAmount` (float): Total margin available for trading
- `unitPercentage` (float): Percentage per unit (default 5%)

**Called By**:
- `initializePosition()`
- `resetSystemToPhase1()`

**CCXT Support**: No - Pure calculation
**MVP Required**: ✅ True

---

### `placeOrder(symbol, side, amount, orderType='market', price=null)`
**Description**: Places orders via CCXT exchange integration. Primary interface between trading system and exchange for order execution.

**Parameters**: 
- `symbol` (string): Trading symbol
- `side` (string): 'buy' or 'sell'
- `amount` (float): Order size
- `orderType` (string): 'market' or 'limit'
- `price` (float): Price for limit orders

**Called By**:
- `executeAllocationChange()`

**CCXT Support**: Yes - Direct CCXT exchange.createOrder() wrapper
**MVP Required**: ✅ True

---

### `validateTrade(symbol, side, amount, availableBalance)`
**Description**: Validates trade feasibility before execution by checking constraints. Prevents invalid trades that could fail at exchange level.

**Parameters**: 
- `symbol` (string): Trading symbol
- `side` (string): Trade direction
- `amount` (float): Trade size
- `availableBalance` (float): Available account balance

**Called By**:
- `executeAllocationChange()`

**CCXT Support**: No - Validation using position data
**MVP Required**: ✅ True

---

### `trackTradeExecution(tradeId, exchangeOrderId, status, executedPrice)`
**Description**: Updates trade status and execution details from exchange callbacks. Maintains accurate trade execution records.

**Parameters**: 
- `tradeId` (integer): Internal trade ID
- `exchangeOrderId` (string): Exchange order ID
- `status` (string): Execution status
- `executedPrice` (float): Actual execution price

**Called By**:
- `executeAllocationChange()`

**CCXT Support**: No - Database update using CCXT callback data
**MVP Required**: ✅ True

---

### `checkFullLongReset(tradingPlanId)`
**Description**: Detects when both allocations reach 100% long and triggers system reset. Enables compound growth through automatic system resets.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan

**Called By**:
- `executeAllocationChange()`

**CCXT Support**: No - Position analysis
**MVP Required**: ✅ True

---

### `updatePeakTracking(newPeakPrice, tradingPlanId)`
**Description**: Updates peak price reference when new highs are reached. Only updates when price exceeds current peak.

**Parameters**: 
- `newPeakPrice` (float): Potential new peak price
- `tradingPlanId` (integer): Database ID of trading plan

**Called By**:
- `resetSystemToPhase1()`

**CCXT Support**: No - Database update
**MVP Required**: ✅ True

---

### `updateValleyTracking(newValleyPrice, tradingPlanId)`
**Description**: Updates valley price reference when new lows are reached. Only updates when price falls below current valley.

**Parameters**: 
- `newValleyPrice` (float): Potential new valley price
- `tradingPlanId` (integer): Database ID of trading plan

**Called By**:
- `resetSystemToPhase1()`

**CCXT Support**: No - Database update
**MVP Required**: ✅ True

---

### `updateUnrealizedPnL(tradingPlanId, currentPrice)`
**Description**: Updates unrealized profit/loss for all positions based on current price. Called on every price update for accurate valuations.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan
- `currentPrice` (float): Current market price

**Called By**:
- `handlePriceUpdate()`

**CCXT Support**: No - Database update
**MVP Required**: ✅ True

---

### `calculatePortfolioValue(tradingPlanId, currentPrice)`
**Description**: Calculates total portfolio value including unrealized P&L. Essential for performance monitoring and reset calculations.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan
- `currentPrice` (float): Current market price

**Called By**:
- `generatePerformanceReport()`

**CCXT Support**: No - Calculation using position data
**MVP Required**: ✅ True

---

### `getPositions()`
**Description**: Fetches current positions from exchange via CCXT and synchronizes with local database. Critical for maintaining accurate state.

**Parameters**: None

**Called By**:
- Various synchronization processes

**CCXT Support**: Yes - Uses exchange.fetchPositions()
**MVP Required**: ✅ True

---

### `getBalance()`
**Description**: Retrieves account balance from exchange. Essential for trade validation and portfolio valuations.

**Parameters**: None

**Called By**:
- Trade validation processes

**CCXT Support**: Yes - Uses exchange.fetchBalance()
**MVP Required**: ✅ True

---

### `cancelOrder(orderId, symbol)`
**Description**: Cancels pending orders via CCXT and updates database status. Used for order management during market changes.

**Parameters**: 
- `orderId` (string): Exchange order ID to cancel
- `symbol` (string): Trading symbol

**Called By**:
- Order management processes

**CCXT Support**: Yes - Uses exchange.cancelOrder()
**MVP Required**: ⭕ False

---

### `calculateRoundTripPnL(entryTrades, exitTrades, fees)`
**Description**: Calculates completed round-trip profit/loss including fees. Used for performance analysis of closed trading cycles.

**Parameters**: 
- `entryTrades` (array): Entry trade records
- `exitTrades` (array): Exit trade records
- `fees` (float): Total fees for the round trip

**Called By**:
- `generatePerformanceReport()`

**CCXT Support**: No - Performance calculation
**MVP Required**: ⭕ False

---

### `handleChoppyConditions(tradingPlanId, priceHistory)`
**Description**: Detects and manages choppy market conditions by analyzing price patterns. Activates tighter trading rules when needed.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan
- `priceHistory` (array): Recent price data

**Called By**:
- Market condition analysis processes

**CCXT Support**: No - Market analysis
**MVP Required**: ⭕ False

---

### `handleExtremeVolatility(tradingPlanId, priceSwings, timeWindow)`
**Description**: Manages extreme volatility by implementing special rules or pausing trading. Prevents excessive trading during high volatility.

**Parameters**: 
- `tradingPlanId` (integer): Database ID of trading plan
- `priceSwings` (array): Recent price movement data
- `timeWindow` (integer): Time period for analysis

**Called By**:
- Volatility management processes

**CCXT Support**: No - Volatility analysis
**MVP Required**: ⭕ False

---

## Function Hierarchy Summary

**Higher-Order Functions**: 7 (Orchestrators)
- MVP Required: 5 (71%)
- CCXT Support: 2 (29%)

**Regular Functions**: 18 (Workers)  
- MVP Required: 13 (72%)
- CCXT Support: 4 (22%)

**Key Orchestration Flows**:
1. **Price Update Flow**: `handlePriceUpdate()` → `calculateUnitsFromReference()` → `determinePhase()` → `executePhaseActions()` → `executeAllocationChange()` → `placeOrder()`

2. **Reset Flow**: `checkFullLongReset()` → `resetSystemToPhase1()` → `calculateUnitValue()` + `updatePeakTracking()` + `updateValleyTracking()`

3. **Trade Execution Flow**: `executeAllocationChange()` → `getAllocations()` + `calculateTradeSize()` + `validateTrade()` + `placeOrder()` + `trackTradeExecution()`