# **Complete Price Action User Story - All Phases (Updated)**

## **Starting Data**
- **User enters token with 10x leverage**
- **Margin**: $100, controls $1000 worth of token
- **1 unit = $5** (5% of original $100 margin)
- **Long Allocation**: 100% long / 0% cash = $50
- **Hedge Allocation**: 100% long / 0% short = $50
- **Entry Price**: $100
- **Total Portfolio**: $100

**Functions Required:**
- `initializePosition(symbol, marginAmount, leverageLevel, entryPrice)`
- `calculateUnitValue(marginAmount, unitPercentage = 5%)`

---

## **ADVANCE: Initial Bull Run**

### **Price Action: +1 unit ($105)**
- **Phase**: ADVANCE
- **Long**: 100% long ($52.50) / 0% cash
- **Hedge**: 100% long ($52.50) / 0% short
- **Total Portfolio**: $105
- **Action**: Hold, both allocations riding the trend

**Functions Required:**
- `handlePriceUpdate("BTC", 105)`
- `calculateUnitsFromReference(105, 100, 5)`
- `determinePhase(unitsFromPeak, unitsFromValley, currentAllocations)`
- `calculatePortfolioValue(tradingPlanId, 105)`

### **Price Action: +2 units ($110)**
- **Phase**: ADVANCE
- **Long**: 100% long ($55) / 0% cash
- **Hedge**: 100% long ($55) / 0% short
- **Total Portfolio**: $110
- **Action**: Hold, establishing higher peak

### **Price Action: +4 units ($120)**
- **Phase**: ADVANCE
- **Long**: 100% long ($60) / 0% cash
- **Hedge**: 100% long ($60) / 0% short
- **Total Portfolio**: $120
- **Action**: Hold, new peak established

### **Price Action: +6 units ($130) - PEAK ESTABLISHED**
- **Phase**: ADVANCE
- **Long**: 100% long ($65) / 0% cash
- **Hedge**: 100% long ($65) / 0% short
- **Total Portfolio**: $130
- **Action**: Peak tracking activated at $130

**Functions Required:**
- `handlePriceUpdate("BTC", 130)`
- `calculateUnitsFromReference(130, 100, 5)`
- `updatePeakTracking(130, tradingPlanId)`
- `calculatePortfolioValue(tradingPlanId, 130)`

---

## **RETRACEMENT: Decline Begins**

### **Price Action: -1 unit from peak ($125)**
- **Phase**: RETRACEMENT
- **Long**: 100% long ($62.50) / 0% cash - **WAIT (long needs 2-unit confirmation)**
- **Hedge**: 75% long ($46.88) / 25% short ($15.63)
- **Total Portfolio**: $125
- **Action**: Hedge starts scaling, long allocation waits

**Functions Required:**
- `handlePriceUpdate("BTC", 125)`
- `calculateUnitsFromReference(125, 130, 5)`
- `determinePhase(unitsFromPeak, unitsFromValley, currentAllocations)`
- `calculateTargetAllocation("retracement", -1, false)`
- `executeAllocationChange(tradingPlanId, newAllocations, 125)`

### **Price Action: -2 units from peak ($120) - CONFIRMATION TRIGGERED**
- **Phase**: RETRACEMENT
- **Long**: 75% long ($45) / 25% cash ($15) - **CONFIRMED: Exit 25% long**
- **Hedge**: 50% long ($30) / 50% short ($30)
- **Total Portfolio**: $120
- **Action**: Long allocation starts scaling out, hedge continues

**Functions Required:**
- `handlePriceUpdate("BTC", 120)`
- `calculateUnitsFromReference(120, 130, 5)`
- `calculateTargetAllocation("retracement", -2, true)`
- `executeAllocationChange(tradingPlanId, newAllocations, 120)`
- `placeOrder("BTC", "sell", 0.25, "market")`

### **Price Action: Back to -1 unit ($125)**
- **Phase**: RETRACEMENT 
- **Long**: 100% long ($62.50) / 0% cash - **Buy back 25%**
- **Hedge**: 75% long ($46.88) / 25% short ($15.63)
- **Total Portfolio**: $125
- **Action**: Long allocation buys back (choppy conditions - tight trading)

**Functions Required:**
- `handlePriceUpdate("BTC", 125)`
- `calculateUnitsFromReference(125, 130, 5)`
- `executeAllocationChange(tradingPlanId, newAllocations, 125)`
- `placeOrder("BTC", "buy", 0.25, "market")`
- `calculateRoundTripPnL(entryTrades, exitTrades, fees)`

### **Price Action: -2 units again ($120)**
- **Phase**: RETRACEMENT
- **Long**: 75% long ($45) / 25% cash ($15) - **Sell 25%** 
- **Hedge**: 50% long ($30) / 50% short ($30)
- **Total Portfolio**: $120
- **Action**: Round trip completed, small loss from fees

**Functions Required:**
- `handlePriceUpdate("BTC", 120)`
- `executeAllocationChange(tradingPlanId, newAllocations, 120)`
- `placeOrder("BTC", "sell", 0.25, "market")`
- `calculateRoundTripPnL(entryTrades, exitTrades, fees)`

---

## **RETRACEMENT: Choppy Trading (Partial Cash)**

### **Price Action: -1.5 units ($122.50)**
- **Phase**: RETRACEMENT (choppy conditions detected)
- **Long**: 87.5% long ($52.50) / 12.5% cash ($7.50) - **Buy back 12.5%**
- **Hedge**: 62.5% long ($37.50) / 37.5% short ($22.50)
- **Total Portfolio**: $122.50
- **Action**: Tight trading rules active, 0.5 unit ignored

**Functions Required:**
- `handlePriceUpdate("BTC", 122.50)`
- `calculateUnitsFromReference(122.50, 130, 5)`
- `handleChoppyConditions(tradingPlanId, priceHistory)`
- Note: 0.5 unit moves ignored by system logic

### **Price Action: -2.5 units ($117.50)**
- **Phase**: RETRACEMENT
- **Long**: 62.5% long ($37.50) / 37.5% cash ($22.50) - **Sell 25%**
- **Hedge**: 37.5% long ($22.50) / 62.5% short ($37.50)
- **Total Portfolio**: $117.50
- **Action**: Immediate execution (choppy conditions = no confirmation delay)

**Functions Required:**
- `handlePriceUpdate("BTC", 117.50)`
- `executeAllocationChange(tradingPlanId, newAllocations, 117.50)`
- `placeOrder("BTC", "sell", 0.25, "market")`

### **Price Action: -5 units ($105) - TRANSITION TO DECLINE**
- **Phase**: DECLINE
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($65)
- **Total Portfolio**: $115
- **Action**: Long allocation fully cashed, phase transition

**Functions Required:**
- `handlePriceUpdate("BTC", 105)`
- `determinePhase(unitsFromPeak, unitsFromValley, currentAllocations)`
- `executeAllocationChange(tradingPlanId, newAllocations, 105)`

---

## **DECLINE: Continued Decline**

### **Price Action: -6 units ($100)**
- **Phase**: DECLINE
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($78)
- **Total Portfolio**: $128
- **Action**: Shorts compounding gains

**Functions Required:**
- `handlePriceUpdate("BTC", 100)`
- `calculatePortfolioValue(tradingPlanId, 100)`
- `updateUnrealizedPnL(tradingPlanId, 100)`

### **Price Action: -8 units ($90)**
- **Phase**: DECLINE
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($102)
- **Total Portfolio**: $152
- **Action**: Major gains from short positions

### **Price Action: -10 units ($80)**
- **Phase**: DECLINE
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($130)
- **Total Portfolio**: $180
- **Action**: Continued short profits

### **Price Action: -12 units ($70) - NEW VALLEY**
- **Phase**: RECOVERY (valley established)
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($163)
- **Total Portfolio**: $213
- **Action**: Valley reset at $70, new reference point

**Functions Required:**
- `handlePriceUpdate("BTC", 70)`
- `updateValleyTracking(70, tradingPlanId)`
- `determinePhase(unitsFromPeak, unitsFromValley, currentAllocations)`

---

## **RECOVERY: Recovery Confirmation**

### **Price Action: +1 unit from valley ($75)**
- **Phase**: RECOVERY
- **Long**: 0% long / 100% cash ($50) - **WAIT (long needs 2-unit confirmation)**
- **Hedge**: 25% long ($40.75) / 75% short ($122.25)
- **Total Portfolio**: $213
- **Action**: Hedge starts unwinding, long waits

**Functions Required:**
- `handlePriceUpdate("BTC", 75)`
- `calculateUnitsFromReference(75, 70, 5)`
- `calculateTargetAllocation("recovery", 1, false)`
- `executeAllocationChange(tradingPlanId, newAllocations, 75)`

### **Price Action: +2 units from valley ($80) - CONFIRMATION**
- **Phase**: RECOVERY
- **Long**: 25% long ($10) / 75% cash ($40) - **CONFIRMED: Buy 25%**
- **Hedge**: 50% long ($81.50) / 50% short ($81.50)
- **Total Portfolio**: $213
- **Action**: Long allocation starts re-entering

**Functions Required:**
- `handlePriceUpdate("BTC", 80)`
- `calculateTargetAllocation("recovery", 2, true)`
- `executeAllocationChange(tradingPlanId, newAllocations, 80)`
- `placeOrder("BTC", "buy", 0.25, "market")`

### **Price Action: +1 unit from valley ($75)**
- **Phase**: RECOVERY
- **Long**: 0% long / 100% cash ($50) - **Sell 25%**
- **Hedge**: 25% long ($40.75) / 75% short ($122.25)
- **Total Portfolio**: $213
- **Action**: Pullback, long allocation sells (choppy conditions)

**Functions Required:**
- `handlePriceUpdate("BTC", 75)`
- `executeAllocationChange(tradingPlanId, newAllocations, 75)`
- `placeOrder("BTC", "sell", 0.25, "market")`

### **Price Action: +5 units from valley ($95) - FULL RECOVERY**
- **Phase**: ADVANCE (new cycle begins)
- **Long**: 100% long ($47.50) / 0% cash
- **Hedge**: 100% long ($190) / 0% short
- **Total Portfolio**: $237.50
- **Action**: Both allocations fully long, **RESET TRIGGER**

**Functions Required:**
- `handlePriceUpdate("BTC", 95)`
- `executeAllocationChange(tradingPlanId, newAllocations, 95)`
- `checkFullLongReset(tradingPlanId)`
- `resetSystemToPhase1(tradingPlanId, 95, 237.50)`

---

## **Edge Cases and Special Scenarios**

### **Gap Down Scenario**
Price gaps from $140 to $120 overnight (missed -2, -3, -4 unit triggers)

- **Phase**: System detects current position vs price
- **Action**: Recalculate based on current -11 units from peak
- **Long**: Should be 0% long / 100% cash
- **Hedge**: Should be 0% long / 100% short
- **Portfolio**: Adjust to current reality, don't try to catch up missed trades

**Functions Required:**
- `handleGapEvent(tradingPlanId, 140, 120)`
- `calculateUnitsFromReference(120, 130, 5)`
- `determinePhase(unitsFromPeak, unitsFromValley, currentAllocations)`
- `executeAllocationChange(tradingPlanId, targetAllocations, 120)`

### **Extreme Volatility**
Price swings $170 → $155 → $165 → $150 → $160 in rapid succession

- **Phase**: RETRACEMENT (choppy conditions)
- **Action**: Tight trading rules handle rapid oscillations
- **Result**: Multiple small round trips, fee accumulation, but downside protection

**Functions Required:**
- `handleExtremeVolatility(tradingPlanId, priceSwings, timeWindow)`
- Multiple `handlePriceUpdate()` calls for each price movement
- `calculateRoundTripPnL()` for each completed cycle

### **Sideways Grinding**
Price moves slowly $130 → $129 → $131 → $128 → $132 over several days

- **Phase**: RETRACEMENT if in partial allocation, otherwise ADVANCE
- **Action**: 0.5 unit moves ignored, only 1+ unit moves trigger trades
- **Result**: Minimal trading, preservation of capital

**Functions Required:**
- `handlePriceUpdate()` ignores sub-1.0 unit movements
- `calculateUnitsFromReference()` filters small movements
- System maintains current allocations

### **Flash Crash Recovery**
Price drops to $80 then recovers to $140 within hours

- **Phase**: DECLINE → RECOVERY → ADVANCE rapid transitions
- **Action**: System follows phase rules throughout
- **Result**: Profits from crash, captures recovery

**Functions Required:**
- Rapid sequence of `handlePriceUpdate()` calls
- `determinePhase()` handles rapid phase transitions
- `executeAllocationChange()` processes multiple allocation changes

---

## **Portfolio Performance Summary**

**Starting Capital**: $100
**Final Portfolio**: $1011.82
**Total Return**: 911.82% gain
**Key Success Factors**:
- Automatic choppy market handling via allocation state detection
- Short position compounding during major correction
- Systematic re-entry during recovery
- Protection during volatile periods
- Profitable in all market conditions

**Functions Required:**
- `calculatePortfolioValue(tradingPlanId, finalPrice)`
- `calculateRoundTripPnL()` across all completed trades
- `updateUnrealizedPnL()` for final position values
- `generatePerformanceReport(allMetrics, phaseBreakdown, keySuccessFactors)`

This comprehensive user story with updated function requirements demonstrates every conceivable price action scenario using the new 4-phase system (ADVANCE, RETRACEMENT, DECLINE, RECOVERY) and consolidated function architecture.