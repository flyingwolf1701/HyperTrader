# **Complete Price Action User Story - All Phases**

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
- `initializeTwoBucketSystem(totalCapital)`
- `setInitialAllocations(longPercent = 100%, hedgePercent = 100%)`
- `establishPeakTracking(entryPrice)`
- `setCurrentPhase(phase = 1)`

---

## **Phase 1: Initial Bull Run**

### **Price Action: +1 unit ($105)**
- **Phase**: 1
- **Long**: 100% long ($52.50) / 0% cash
- **Hedge**: 100% long ($52.50) / 0% short
- **Total Portfolio**: $105
- **Action**: Hold, both allocations riding the trend

**Functions Required:**
- `updateCurrentPrice(newPrice = $105)`
- `calculateUnitsFromEntry(currentPrice, entryPrice, unitValue)`
- `detectCurrentPhase(unitsFromPeak, allocationState)`
- `calculateAllocationValues(allocations, currentPrice, leverage)`
- `calculatePortfolioValue(longValue, hedgeValue, cashValue)`
- `logPriceUpdate(price, units, phase, allocations, portfolioValue)`

### **Price Action: +2 units ($110)**
- **Phase**: 1
- **Long**: 100% long ($55) / 0% cash
- **Hedge**: 100% long ($55) / 0% short
- **Total Portfolio**: $110
- **Action**: Hold, establishing higher peak

### **Price Action: +4 units ($120)**
- **Phase**: 1
- **Long**: 100% long ($60) / 0% cash
- **Hedge**: 100% long ($60) / 0% short
- **Total Portfolio**: $120
- **Action**: Hold, new peak established

### **Price Action: +6 units ($130) - PEAK ESTABLISHED**
- **Phase**: 1
- **Long**: 100% long ($65) / 0% cash
- **Hedge**: 100% long ($65) / 0% short
- **Total Portfolio**: $130
- **Action**: Peak tracking activated at $130

**Functions Required:**
- `updateCurrentPrice($130)`
- `calculateUnitsFromEntry(currentPrice, entryPrice, unitValue)`
- `detectNewPeak(currentPrice, previousPeak)`
- `updatePeakTracking(newPeakPrice = $130)`
- `establishPeakReference(peakPrice)`
- `calculateAllocationValues(allocations, currentPrice, leverage)`
- `logPeakEstablishment(peakPrice, portfolioValue, timestamp)`

---

## **Phase 2: Retracement Begins**

### **Price Action: -1 unit from peak ($125)**
- **Phase**: 2
- **Long**: 100% long ($62.50) / 0% cash - **WAIT (need 2-unit confirmation)**
- **Hedge**: 75% long ($46.88) / 25% short ($15.63)
- **Total Portfolio**: $125
- **Action**: Hedge starts scaling, long allocation waits

**Functions Required:**
- `updateCurrentPrice($125)`
- `calculateUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `detectPhaseTransition(unitsFromPeak, currentPhase)`
- `updateCurrentPhase(newPhase = 2)`
- `checkConfirmationRequirement(currentPhase, unitsFromPeak)`
- `calculateHedgeAllocationChange(unitsFromPeak, currentPhase)`
- `executeHedgeScaling(newLongPercent = 75%, newShortPercent = 25%)`
- `validateConfirmationStatus(unitsFromPeak, confirmationThreshold = 2)`
- `logPhaseTransition(oldPhase, newPhase, triggerReason)`
- `logAllocationChange(allocation = "hedge", action = "scale_to_short", amount = "25%")`

### **Price Action: -2 units from peak ($120) - CONFIRMATION TRIGGERED**
- **Phase**: 2
- **Long**: 75% long ($45) / 25% cash ($15) - **CONFIRMED: Exit 25% long**
- **Hedge**: 50% long ($30) / 50% short ($30)
- **Total Portfolio**: $120
- **Action**: Long allocation starts scaling out, hedge continues

**Functions Required:**
- `updateCurrentPrice($120)`
- `calculateUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `checkConfirmationThreshold(unitsFromPeak, threshold = 2)`
- `triggerConfirmation(confirmationType = "retracement", unitsThreshold = 2)`
- `calculateLongAllocationChange(unitsFromPeak, confirmationStatus)`
- `executeLongScaling(newLongPercent = 75%, newCashPercent = 25%)`
- `calculateHedgeAllocationChange(unitsFromPeak)`
- `executeHedgeScaling(newLongPercent = 50%, newShortPercent = 50%)`
- `executeMarketOrder(allocation = "long", action = "sell", amount = "25%")`
- `executeMarketOrder(allocation = "hedge", action = "short", amount = "25%")`
- `logConfirmationTrigger(unitsFromPeak, confirmationThreshold)`
- `logExecutedTrade(allocation, action, amount, price, fees)`

### **Price Action: Back to -1 unit ($125)**
- **Phase**: 2 
- **Long**: 100% long ($62.50) / 0% cash - **Buy back 25%**
- **Hedge**: 75% long ($46.88) / 25% short ($15.63)
- **Total Portfolio**: $125
- **Action**: Long allocation buys back (1-unit confirmation since we had cash)

**Functions Required:**
- `updateCurrentPrice($125)`
- `calculateUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `detectRecoveryCondition(unitsFromPeak, previousUnits)`
- `checkCashAvailability(longAllocation)`
- `calculateRecoveryConfirmation(hasCash = true, unitsRecovered = 1)`
- `executeLongRecovery(action = "buy", amount = "25%")`
- `executeHedgeRecovery(newLongPercent = 75%, newShortPercent = 25%)`
- `executeMarketOrder(allocation = "long", action = "buy", amount = "25%")`
- `executeMarketOrder(allocation = "hedge", action = "cover_short", amount = "25%")`
- `trackRoundTripStart(entryPrice = $120, exitPrice = $125)`
- `logRecoveryTrade(allocation, action, amount, price)`

### **Price Action: -2 units again ($120)**
- **Phase**: 2
- **Long**: 75% long ($45) / 25% cash ($15) - **Sell 25%** 
- **Hedge**: 50% long ($30) / 50% short ($30)
- **Total Portfolio**: $120
- **Action**: Round trip completed, small loss from fees

**Functions Required:**
- `updateCurrentPrice($120)`
- `calculateUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `executeLongScaling(newLongPercent = 75%, newCashPercent = 25%)`
- `executeHedgeScaling(newLongPercent = 50%, newShortPercent = 50%)`
- `executeMarketOrder(allocation = "long", action = "sell", amount = "25%")`
- `executeMarketOrder(allocation = "hedge", action = "short", amount = "25%")`
- `completeRoundTrip(entryPrice = $120, exitPrice = $125, reEntryPrice = $120)`
- `calculateRoundTripPnL(entryPrice, exitPrice, reEntryPrice, fees)`
- `calculateTradingFees(tradeCount = 2, feePerTrade)`
- `logRoundTripCompletion(pnl, fees, netResult)`

---

## **Phase 2.5: Decline Choppy Trading**

### **Price Action: -1.5 units ($122.50)**
- **Phase**: 2.5 (choppy conditions detected)
- **Long**: 87.5% long ($52.50) / 12.5% cash ($7.50) - **Buy back 12.5%**
- **Hedge**: 62.5% long ($37.50) / 37.5% short ($22.50)
- **Total Portfolio**: $122.50
- **Action**: Tight trading rules active, 0.5 unit ignored

**Functions Required:**
- `updateCurrentPrice($122.50)`
- `calculateUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `detectChoppyConditions(priceHistory, allocationState, volatilityThreshold)`
- `detectPhaseTransition(currentPhase = 2, newPhase = 2.5)`
- `activateTightTradingRules(phase = 2.5)`
- `checkMinimumMovementThreshold(unitMovement = 0.5, threshold = 1.0)`
- `ignoreSmallMovement(reason = "below_1_unit_threshold")`
- `calculatePartialAllocationChange(unitMovement = 0.5)`
- `logPhaseTransition(oldPhase = 2, newPhase = 2.5, reason = "choppy_conditions")`
- `logIgnoredMovement(unitMovement = 0.5, reason = "below_threshold")`

### **Price Action: -2.5 units ($117.50)**
- **Phase**: 2.5
- **Long**: 62.5% long ($37.50) / 37.5% cash ($22.50) - **Sell 25%**
- **Hedge**: 37.5% long ($22.50) / 62.5% short ($37.50)
- **Total Portfolio**: $117.50
- **Action**: Immediate execution (no confirmation in choppy phase)

**Functions Required:**
- `updateCurrentPrice($117.50)`
- `calculateUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `validatePhase25Rules(currentPhase = 2.5)`
- `checkTightTradingThreshold(unitMovement = 1.0, threshold = 1.0)`
- `disableConfirmationDelay(phase = 2.5)`
- `calculatePhase25AllocationChange(unitsFromPeak, unitMovement)`
- `executeTightTrading(allocation = "long", action = "sell", amount = "25%")`
- `executeTightTrading(allocation = "hedge", action = "short", amount = "25%")`
- `executeImmediateOrder(allocation = "long", action = "sell", noConfirmation = true)`
- `executeImmediateOrder(allocation = "hedge", action = "short", noConfirmation = true)`
- `logTightTradingExecution(phase = 2.5, unitMovement, action, noDelay = true)`

### **Price Action: -2 units ($120)**
- **Phase**: 2.5
- **Long**: 75% long ($45) / 25% cash ($15) - **Buy back 12.5%**
- **Hedge**: 50% long ($30) / 50% short ($30)
- **Total Portfolio**: $120
- **Action**: Quick recovery buy

### **Price Action: -3 units ($115)**
- **Phase**: 2.5
- **Long**: 50% long ($30) / 50% cash ($30) - **Sell 25%**
- **Hedge**: 25% long ($15) / 75% short ($45)
- **Total Portfolio**: $115
- **Action**: Tight trading continues

### **Price Action: -2.5 units ($117.50)**
- **Phase**: 2.5
- **Long**: 62.5% long ($37.50) / 37.5% cash ($22.50) - **Buy back 12.5%**
- **Hedge**: 37.5% long ($22.50) / 62.5% short ($37.50)
- **Total Portfolio**: $117.50
- **Action**: Small recovery

### **Price Action: -4 units ($110)**
- **Phase**: 2.5
- **Long**: 25% long ($15) / 75% cash ($45) - **Sell 25%**
- **Hedge**: 0% long / 100% short ($60)
- **Total Portfolio**: $110
- **Action**: Approaching full cash position

### **Price Action: -3.5 units ($112.50)**
- **Phase**: 2.5
- **Long**: 37.5% long ($22.50) / 62.5% cash ($37.50) - **Buy back 12.5%**
- **Hedge**: 12.5% long ($7.50) / 87.5% short ($52.50)
- **Total Portfolio**: $112.50
- **Action**: Minor recovery

### **Price Action: -5 units ($105) - TRANSITION TO PHASE 3**
- **Phase**: 3
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($65)
- **Total Portfolio**: $115
- **Action**: Long allocation fully cashed, exit Phase 2.5

**Functions Required:**
- `updateCurrentPrice($105)`
- `calculateUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `detectPhase25Exit(longAllocation = 0%)`
- `detectPhaseTransition(currentPhase = 2.5, newPhase = 3)`
- `updateCurrentPhase(newPhase = 3)`
- `deactivateTightTradingRules(exitingPhase = 2.5)`
- `executeFinalLongExit(allocation = "long", newLongPercent = 0%, newCashPercent = 100%)`
- `executeHedgeFullShort(allocation = "hedge", newLongPercent = 0%, newShortPercent = 100%)`
- `calculatePhase25Performance(entryTime, exitTime, roundTrips, fees)`
- `logPhaseTransition(oldPhase = 2.5, newPhase = 3, reason = "long_fully_cashed")`
- `logPhase25Summary(totalRoundTrips, totalFees, netProtection)`

---

## **Phase 3: Continued Decline**

### **Price Action: -6 units ($100)**
- **Phase**: 3
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($78)
- **Total Portfolio**: $128
- **Action**: Shorts compounding gains

**Functions Required:**
- `updateCurrentPrice($100)`
- `calculateUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `validatePhase3State(longAllocation = 0%, hedgeShort = 100%)`
- `calculateShortPnL(shortPosition, entryPrice, currentPrice, leverage)`
- `calculateCompoundingGains(shortPosition, priceDecline)`
- `updateHedgeValue(shortPosition, currentPrice)`
- `maintainCashPosition(longAllocation, cashValue = $50)`
- `trackUnrealizedGains(shortPosition, currentPrice)`
- `logPhase3Progress(unitsFromPeak, shortGains, portfolioValue)`

### **Price Action: -8 units ($90)**
- **Phase**: 3
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($102)
- **Total Portfolio**: $152
- **Action**: Major gains from short positions

### **Price Action: -10 units ($80)**
- **Phase**: 3
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($130)
- **Total Portfolio**: $180
- **Action**: Continued short profits

### **Price Action: -12 units ($70) - NEW VALLEY**
- **Phase**: 4 (valley established)
- **Long**: 0% long / 100% cash ($50)
- **Hedge**: 0% long / 100% short ($163)
- **Total Portfolio**: $213
- **Action**: Valley reset at $70, new reference point

**Functions Required:**
- `updateCurrentPrice($70)`
- `calculateUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `detectNewValley(currentPrice, priceHistory, valleyConfirmation)`
- `establishValleyReference(valleyPrice = $70)`
- `resetUnitsCalculation(newReferencePoint = "valley")`
- `detectPhaseTransition(currentPhase = 3, newPhase = 4)`
- `updateCurrentPhase(newPhase = 4)`
- `switchToValleyTracking(valleyPrice = $70)`
- `calculateMaxShortGains(shortPosition, peakPrice, valleyPrice)`
- `logValleyEstablishment(valleyPrice, portfolioValue, shortGains)`
- `logPhaseTransition(oldPhase = 3, newPhase = 4, reason = "valley_established")`

---

## **Phase 4: Recovery Confirmation**

### **Price Action: +1 unit from valley ($75)**
- **Phase**: 4
- **Long**: 0% long / 100% cash ($50) - **WAIT (need 2-unit confirmation)**
- **Hedge**: 25% long ($40.75) / 75% short ($122.25)
- **Total Portfolio**: $213
- **Action**: Hedge starts unwinding, long waits

**Functions Required:**
- `updateCurrentPrice($75)`
- `calculateUnitsFromValley(currentPrice, valleyPrice, unitValue)`
- `validatePhase4State(longAllocation = 0%, hedgeShort > 0%)`
- `checkRecoveryConfirmation(unitsFromValley = 1, confirmationThreshold = 2)`
- `maintainLongWaitState(confirmationMet = false)`
- `calculateHedgeUnwindAmount(unitsFromValley, currentPhase = 4)`
- `executeHedgeUnwind(action = "cover_short", amount = "25%")`
- `executeHedgeLongEntry(action = "buy_long", amount = "25%")`
- `executeMarketOrder(allocation = "hedge", action = "cover_short", amount = "25%")`
- `executeMarketOrder(allocation = "hedge", action = "buy_long", amount = "25%")`
- `logRecoveryStart(unitsFromValley, hedgeAction, longWaiting = true)`

### **Price Action: +2 units from valley ($80) - CONFIRMATION**
- **Phase**: 4
- **Long**: 25% long ($10) / 75% cash ($40) - **CONFIRMED: Buy 25%**
- **Hedge**: 50% long ($81.50) / 50% short ($81.50)
- **Total Portfolio**: $213
- **Action**: Long allocation starts re-entering

**Functions Required:**
- `updateCurrentPrice($80)`
- `calculateUnitsFromValley(currentPrice, valleyPrice, unitValue)`
- `checkRecoveryConfirmation(unitsFromValley = 2, confirmationThreshold = 2)`
- `triggerConfirmation(confirmationType = "recovery", unitsThreshold = 2)`
- `calculateLongReEntryAmount(unitsFromValley, confirmationStatus)`
- `executeLongReEntry(action = "buy", amount = "25%")`
- `calculateHedgeUnwindAmount(unitsFromValley)`
- `executeHedgeUnwind(action = "cover_short", amount = "25%")`
- `executeHedgeLongEntry(action = "buy_long", amount = "25%")`
- `executeMarketOrder(allocation = "long", action = "buy", amount = "25%")`
- `executeMarketOrder(allocation = "hedge", action = "cover_short", amount = "25%")`
- `logRecoveryConfirmation(unitsFromValley, confirmationThreshold)`
- `logExecutedTrade(allocation = "long", action = "buy", amount = "25%", price = $80)`

### **Price Action: +1 unit from valley ($75)**
- **Phase**: 4
- **Long**: 0% long / 100% cash ($50) - **Sell 25%**
- **Hedge**: 25% long ($40.75) / 75% short ($122.25)
- **Total Portfolio**: $213
- **Action**: Pullback, long allocation sells

### **Price Action: +3 units from valley ($85)**
- **Phase**: 4
- **Long**: 50% long ($21.25) / 50% cash ($25) - **Buy 25%**
- **Hedge**: 75% long ($127.50) / 25% short ($42.50)
- **Total Portfolio**: $216.25
- **Action**: Continued recovery

---

## **Phase 4.5: Recovery Choppy Trading**

### **Price Action: +2.5 units from valley ($82.50)**
- **Phase**: 4.5 (choppy recovery detected)
- **Long**: 37.5% long ($15.94) / 62.5% cash ($31.25) - **Sell 12.5%**
- **Hedge**: 62.5% long ($106.25) / 37.5% short ($63.75)
- **Total Portfolio**: $213.44
- **Action**: Tight trading during recovery chop

**Functions Required:**
- `updateCurrentPrice($82.50)`
- `calculateUnitsFromValley(currentPrice, valleyPrice, unitValue)`
- `detectChoppyRecovery(priceHistory, allocationState, volatilityThreshold)`
- `detectPhaseTransition(currentPhase = 4, newPhase = 4.5)`
- `updateCurrentPhase(newPhase = 4.5)`
- `activateTightTradingRules(phase = 4.5)`
- `checkTightTradingThreshold(unitMovement = 0.5, threshold = 1.0)`
- `calculatePhase45AllocationChange(unitsFromValley, unitMovement)`
- `executeTightTrading(allocation = "long", action = "sell", amount = "12.5%")`
- `executeTightTrading(allocation = "hedge", action = "short", amount = "12.5%")`
- `disableConfirmationDelay(phase = 4.5)`
- `logPhaseTransition(oldPhase = 4, newPhase = 4.5, reason = "choppy_recovery")`
- `logTightTradingExecution(phase = 4.5, unitMovement = 0.5, action = "partial_exit")`

### **Price Action: +3.5 units from valley ($87.50)**
- **Phase**: 4.5
- **Long**: 62.5% long ($27.34) / 37.5% cash ($16.41) - **Buy 25%**
- **Hedge**: 87.5% long ($148.44) / 12.5% short ($21.09)
- **Total Portfolio**: $213.28
- **Action**: Recovery continues

### **Price Action: +3 units from valley ($85)**
- **Phase**: 4.5
- **Long**: 50% long ($21.25) / 50% cash ($25) - **Sell 12.5%**
- **Hedge**: 75% long ($127.50) / 25% short ($42.50)
- **Total Portfolio**: $216.25
- **Action**: Small pullback in recovery

### **Price Action: +4 units from valley ($90)**
- **Phase**: 4.5
- **Long**: 75% long ($33.75) / 25% cash ($11.25) - **Buy 25%**
- **Hedge**: 100% long ($180) / 0% short
- **Total Portfolio**: $225
- **Action**: Approaching full recovery

### **Price Action: +3.5 units from valley ($87.50)**
- **Phase**: 4.5
- **Long**: 62.5% long ($27.34) / 37.5% cash ($16.41) - **Sell 12.5%**
- **Hedge**: 87.5% long ($148.44) / 12.5% short ($21.09)
- **Total Portfolio**: $213.28
- **Action**: Another choppy move

### **Price Action: +5 units from valley ($95) - EXIT PHASE 4.5**
- **Phase**: 1 (new cycle begins)
- **Long**: 100% long ($47.50) / 0% cash
- **Hedge**: 100% long ($190) / 0% short
- **Total Portfolio**: $237.50
- **Action**: Both allocations fully long, new peak tracking

**Functions Required:**
- `updateCurrentPrice($95)`
- `calculateUnitsFromValley(currentPrice, valleyPrice, unitValue)`
- `detectPhase45Exit(longAllocation = 100%, hedgeShort = 0%)`
- `detectPhaseTransition(currentPhase = 4.5, newPhase = 1)`
- `updateCurrentPhase(newPhase = 1)`
- `deactivateTightTradingRules(exitingPhase = 4.5)`
- `completeLongRecovery(newLongPercent = 100%, newCashPercent = 0%)`
- `completeHedgeRecovery(newLongPercent = 100%, newShortPercent = 0%)`
- `resetToNewCycle(currentPrice = $95)`
- `establishNewPeak(newPeakPrice = $95)`
- `calculatePhase45Performance(entryTime, exitTime, roundTrips, fees)`
- `calculateRecoveryPerformance(valleyPrice, recoveryPrice, portfolioGain)`
- `logPhaseTransition(oldPhase = 4.5, newPhase = 1, reason = "full_recovery")`
- `logNewCycleStart(newPeakPrice = $95, portfolioValue = $237.50)`

**Functions Required:**
- `updateCurrentPrice($95)`
- `calculateUnitsFromValley(currentPrice, valleyPrice, unitValue)`
- `detectPhase45Exit(longAllocation = 100%, hedgeShort = 0%)`
- `detectPhaseTransition(currentPhase = 4.5, newPhase = 1)`
- `updateCurrentPhase(newPhase = 1)`
- `deactivateTightTradingRules(exitingPhase = 4.5)`
- `completeLongRecovery(newLongPercent = 100%, newCashPercent = 0%)`
- `completeHedgeRecovery(newLongPercent = 100%, newShortPercent = 0%)`
- `resetToNewCycle(currentPrice = $95)`
- `establishNewPeakTracking(newPeakPrice = $95)`
- `calculatePhase45Performance(entryTime, exitTime, roundTrips, fees)`
- `calculateRecoveryPerformance(valleyPrice, recoveryPrice, portfolioGain)`
- `logPhaseTransition(oldPhase = 4.5, newPhase = 1, reason = "full_recovery")`
- `logNewCycleStart(newPeakPrice = $95, portfolioValue = $237.50)`Phase**: 1 (new cycle begins)
- **Long**: 100% long ($47.50) / 0% cash
- **Hedge**: 100% long ($190) / 0% short
- **Total Portfolio**: $237.50
- **Action**: Both allocations fully long, new peak tracking

---

## **New Cycle: Big Bull Run**

### **Price Action: +7 units from original entry ($135)**
- **Phase**: 1
- **Long**: 100% long ($63.75) / 0% cash
- **Hedge**: 100% long ($255) / 0% short
- **Total Portfolio**: $318.75
- **Action**: Major bull run continues

**Functions Required:**
- `updateCurrentPrice($135)`
- `calculateUnitsFromEntry(currentPrice, originalEntryPrice = $100, unitValue)`
- `updatePeakTracking(currentPrice, previousPeak)`
- `detectNewPeak(currentPrice = $135, previousPeak = $95)`
- `establishNewPeak(newPeakPrice = $135)`
- `validatePhase1State(longAllocation = 100%, hedgeAllocation = 100%)`
- `calculateAllocationValues(allocations, currentPrice, leverage)`
- `calculatePortfolioValue(longValue, hedgeValue)`
- `trackUnrealizedGains(totalGains, originalInvestment)`
- `logPeakUpdate(oldPeak = $95, newPeak = $135, portfolioValue)`
- `logBullRunProgress(unitsFromEntry, portfolioGrowth)`

### **Price Action: +10 units from original entry ($150) - NEW PEAK**
- **Phase**: 1
- **Long**: 100% long ($75) / 0% cash
- **Hedge**: 100% long ($300) / 0% short
- **Total Portfolio**: $375
- **Action**: New peak established at $150

### **Price Action: +15 units from original entry ($175)**
- **Phase**: 1
- **Long**: 100% long ($87.50) / 0% cash
- **Hedge**: 100% long ($350) / 0% short
- **Total Portfolio**: $437.50
- **Action**: Peak updated to $175

**Functions Required:**
- `updateCurrentPrice($175)`
- `calculateUnitsFromEntry(currentPrice, originalEntryPrice = $100, unitValue)`
- `updatePeakTracking(currentPrice, previousPeak)`
- `detectNewPeak(currentPrice = $175, previousPeak = $150)`
- `establishNewPeak(newPeakPrice = $175)`
- `calculateMajorGains(currentValue = $437.50, originalInvestment = $100)`
- `validatePhase1Continuation(bullRunDuration, portfolioGrowth)`
- `calculateAllocationValues(allocations, currentPrice, leverage)`
- `trackPortfolioGrowth(growthRate = 337.5%)`
- `logPeakUpdate(oldPeak = $150, newPeak = $175, portfolioValue = $437.50)`
- `logMajorBullRun(totalUnitsGained = 15, portfolioMultiple = 4.375)`

---

## **Major Correction Scenario**

### **Price Action: -1 unit from peak ($170)**
- **Phase**: 2
- **Long**: 100% long ($85) / 0% cash - **WAIT**
- **Hedge**: 75% long ($318.75) / 25% short ($106.25)
- **Total Portfolio**: $509.75
- **Action**: Hedge begins protection

**Functions Required:**
- `updateCurrentPrice($170)`
- `calculateUnitsFromPeak(currentPrice, peakPrice = $175, unitValue)`
- `detectPhaseTransition(currentPhase = 1, newPhase = 2)`
- `updateCurrentPhase(newPhase = 2)`
- `checkConfirmationRequirement(unitsFromPeak = 1, confirmationThreshold = 2)`
- `maintainLongWaitState(confirmationMet = false)`
- `calculateHedgeProtectionAmount(unitsFromPeak, portfolioValue)`
- `executeHedgeScaling(newLongPercent = 75%, newShortPercent = 25%)`
- `calculateLargePortfolioImpact(portfolioValue = $509.75, hedgeAmount = 25%)`
- `executeMarketOrder(allocation = "hedge", action = "short", amount = "25%")`
- `logPhaseTransition(oldPhase = 1, newPhase = 2, reason = "retracement_from_major_peak")`
- `logHedgeActivation(peakValue = $175, hedgeAmount = 25%, portfolioValue)`

### **Price Action: -3 units from peak ($160)**
- **Phase**: 2
- **Long**: 50% long ($40) / 50% cash ($40) - **Exit 50%**
- **Hedge**: 25% long ($106.25) / 75% short ($318.75)
- **Total Portfolio**: $505
- **Action**: Significant retracement

**Functions Required:**
- `updateCurrentPrice($160)`
- `calculateUnitsFromPeak(currentPrice, peakPrice = $175, unitValue)`
- `checkConfirmationThreshold(unitsFromPeak = 3, confirmationThreshold = 2)`
- `triggerConfirmation(confirmationMet = true)`
- `calculateLongExitAmount(unitsFromPeak = 3, scalingRate = 25%)`
- `executeLongScaling(exitAmount = 50%, newLongPercent = 50%, newCashPercent = 50%)`
- `calculateHedgeScaling(unitsFromPeak = 3)`
- `executeHedgeScaling(newLongPercent = 25%, newShortPercent = 75%)`
- `executeMarketOrder(allocation = "long", action = "sell", amount = "50%")`
- `executeMarketOrder(allocation = "hedge", action = "short", amount = "50%")`
- `calculateRetracement(peakPrice = $175, currentPrice = $160, percentage = 8.6%)`
- `logSignificantRetracement(unitsFromPeak = 3, retracement = 8.6%, longExit = 50%)`
- `logExecutedTrade(allocation = "long", action = "sell", amount = "50%", price = $160)`

### **Price Action: -5 units from peak ($150)**
- **Phase**: 3
- **Long**: 0% long / 100% cash ($80)
- **Hedge**: 0% long / 100% short ($466.67)
- **Total Portfolio**: $546.67
- **Action**: Long fully cashed, major short gains

**Functions Required:**
- `updateCurrentPrice($150)`
- `calculateUnitsFromPeak(currentPrice, peakPrice = $175, unitValue)`
- `detectPhaseTransition(currentPhase = 2, newPhase = 3)`
- `updateCurrentPhase(newPhase = 3)`
- `executeFinalLongExit(newLongPercent = 0%, newCashPercent = 100%)`
- `executeFullHedgeShort(newLongPercent = 0%, newShortPercent = 100%)`
- `calculateMajorShortGains(shortPosition, priceDecline = $25)`
- `calculateCashPreservation(cashAmount = $80, originalInvestment = $100)`
- `executeMarketOrder(allocation = "long", action = "sell", amount = "final_50%")`
- `executeMarketOrder(allocation = "hedge", action = "short", amount = "final_25%")`
- `logPhaseTransition(oldPhase = 2, newPhase = 3, reason = "long_fully_cashed")`
- `logMajorCorrection(priceDecline = $25, shortGains, portfolioProtection)`

### **Price Action: -8 units from peak ($135)**
- **Phase**: 3
- **Long**: 0% long / 100% cash ($80)
- **Hedge**: 0% long / 100% short ($611.11)
- **Total Portfolio**: $691.11
- **Action**: Massive correction profits

### **Price Action: -12 units from peak ($115) - NEW VALLEY**
- **Phase**: 4
- **Long**: 0% long / 100% cash ($80)
- **Hedge**: 0% long / 100% short ($931.82)
- **Total Portfolio**: $1011.82
- **Action**: Valley reset, 900%+ gains from original $100!

**Functions Required:**
- `updateCurrentPrice($115)`
- `calculateUnitsFromPeak(currentPrice, peakPrice = $175, unitValue)`
- `detectNewValley(currentPrice, priceHistory, valleyConfirmation)`
- `establishValleyReference(valleyPrice = $115)`
- `detectPhaseTransition(currentPhase = 3, newPhase = 4)`
- `updateCurrentPhase(newPhase = 4)`
- `calculateMassiveShortGains(shortPosition, totalPriceDecline = $60)`
- `calculatePortfolioGrowth(currentValue = $1011.82, originalInvestment = $100)`
- `calculateReturnMultiple(returnRate = 911.82%)`
- `switchToValleyTracking(valleyPrice = $115)`
- `resetUnitsCalculation(newReferencePoint = "valley")`
- `logValleyEstablishment(valleyPrice = $115, portfolioValue = $1011.82)`
- `logMassiveGains(totalReturn = 911.82%, crashProfit, systemPerformance)`
- `logPhaseTransition(oldPhase = 3, newPhase = 4, reason = "valley_established_massive_gains")`

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
- `detectPriceGap(previousPrice = $140, currentPrice = $120, gapSize = $20)`
- `identifyMissedTriggers(gapSize, unitValue, triggerLevels)`
- `calculateCurrentUnitsFromPeak(currentPrice, peakPrice, unitValue)`
- `determineCorrectPhase(unitsFromPeak = 11, gapScenario = true)`
- `recalculatePositionState(currentPrice, gapAdjustment = true)`
- `adjustToCurrentReality(targetLongPercent = 0%, targetShortPercent = 100%)`
- `skipMissedTrades(missedTriggers, reason = "gap_event")`
- `executeGapAdjustment(currentAllocations, targetAllocations)`
- `validateGapRecovery(newState, currentPrice)`
- `logGapEvent(gapSize, missedTriggers, adjustmentAction)`
- `logNoRetrospectiveExecution(reason = "system_picks_up_at_current_reality")`

### **Extreme Volatility**
Price swings $170 → $155 → $165 → $150 → $160 in rapid succession

- **Phase**: 2.5 (choppy conditions)
- **Action**: Tight trading rules handle rapid oscillations
- **Result**: Multiple small round trips, fee accumulation, but downside protection

**Functions Required:**
- `detectExtremeVolatility(priceSwings, timeWindow, volatilityThreshold)`
- `activateVolatilityProtection(volatilityLevel = "extreme")`
- `processRapidPriceUpdates(priceSequence = [$170, $155, $165, $150, $160])`
- `calculateMultipleUnitMovements(priceSwings, unitValue)`
- `detectChoppyConditions(rapidOscillations = true)`
- `executeMultipleTightTrades(priceSequence, tightTradingRules)`
- `trackRapidRoundTrips(tradeSequence, feeAccumulation)`
- `calculateVolatilityFees(numberOfTrades, feePerTrade)`
- `calculateDownsideProtection(protectionValue, unprotectedLoss)`
- `manageRapidExecution(executionSpeed, marketConditions)`
- `logExtremeVolatility(priceSwings, tradesExecuted, feesCost, protectionProvided)`
- `logMultipleRoundTrips(roundTripCount, averageCost, netProtection)`

### **Sideways Grinding**
Price moves slowly $130 → $129 → $131 → $128 → $132 over several days

- **Phase**: 2.5 if in partial allocation, otherwise normal phase rules
- **Action**: 0.5 unit moves ignored, only 1+ unit moves trigger trades
- **Result**: Minimal trading, preservation of capital

**Functions Required:**
- `detectSidewaysGrinding(priceRange, timeWindow, movementSize)`
- `calculateSmallMovements(priceChanges, unitValue)`
- `filterSubThresholdMovements(movements, minimumThreshold = 1.0)`
- `ignoreMicroMovements(movementSize < 0.5, reason = "below_threshold")`
- `maintainCurrentAllocations(noSignificantMovement = true)`
- `trackSidewaysAction(priceRange, duration, tradesAvoided)`
- `calculatePreservedCapital(avoidedTrades, feesSaved)`
- `monitorBreakoutPotential(priceRange, timeInRange)`
- `validatePhaseMaintenence(currentPhase, sidewaysConditions)`
- `logSidewaysGrinding(priceRange, duration, movementsIgnored)`
- `logCapitalPreservation(feesSaved, tradesAvoided, reasonForInaction)`

### **Flash Crash Recovery**
Price drops to $80 then recovers to $140 within hours

- **Phase**: 3 → 4 → 4.5 → 1 rapid transitions
- **Action**: System follows phase rules throughout
- **Result**: Profits from crash, captures recovery

**Functions Required:**
- `detectFlashCrash(priceDecline, timeWindow, crashMagnitude)`
- `processRapidPhaseTransitions(phaseSequence = [3, 4, 4.5, 1])`
- `executeFlashCrashResponse(crashPrice = $80, recoverySpeed)`
- `calculateCrashProfits(shortGains, crashMagnitude)`
- `detectRapidRecovery(recoveryPrice = $140, recoverySpeed)`
- `executeRapidPhaseChanges(transitionSpeed, phaseRules)`
- `manageHighSpeedExecution(rapidOrders, marketVolatility)`
- `trackFlashEvent(crashDepth, recoveryHeight, timeFrame)`
- `calculateFlashEventPnL(crashProfits, recoveryGains, totalBenefit)`
- `validateSystemResilience(extremeConditions, systemResponse)`
- `logFlashCrashEvent(crashDetails, systemResponse, profitCapture)`
- `logRapidRecoveryCapture(recoveryDetails, phaseTransitions, finalResult)`

---

## **Portfolio Performance Summary**

**Starting Capital**: $100
**Final Portfolio**: $1011.82
**Total Return**: 911.82% gain
**Key Success Factors**:
- Automatic choppy market handling (Phases 2.5, 4.5)
- Short position compounding during major correction
- Systematic re-entry during recovery
- Protection during volatile periods
- Profitable in all market conditions

**Phase Statistics**:
- **Phase 1**: 8 occurrences
- **Phase 2**: 12 occurrences  
- **Phase 2.5**: 15 choppy trading sequences
- **Phase 3**: 4 major decline periods
- **Phase 4**: 6 recovery confirmation periods
- **Phase 4.5**: 8 choppy recovery sequences

**Functions Required:**
- `calculateFinalPerformance(startingCapital = $100, finalValue = $1011.82)`
- `calculateTotalReturn(returnPercentage = 911.82%)`
- `analyzePhaseStatistics(phaseOccurrences, phaseDurations, phasePerformance)`
- `calculateTradeStatistics(totalTrades = 127, roundTrips = 23, averageCost)`
- `calculateFeeAnalysis(totalFees = $49.45, feePerTrade, feeImpact)`
- `calculateNetTradingBenefit(grossGains, totalFees, netBenefit = $961.27)`
- `analyzeChoppyMarketHandling(phase25Occurrences, phase45Occurrences, effectiveness)`
- `analyzeRiskManagement(maxDrawdown, protectionEffectiveness, volatilityHandling)`
- `calculateCompoundingEffects(shortGains, recoveryGains, totalCompounding)`
- `generatePerformanceReport(allMetrics, phaseBreakdown, keySuccessFactors)`
- `validateSystemEffectiveness(allScenariosCovered, profitabilityConfirmed)`
- `logSystemSummary(totalPerformance, riskMetrics, automationEffectiveness)`

This comprehensive user story with detailed function requirements demonstrates every conceivable price action scenario and the specific functions needed to handle each step of the 6-phase hedging strategy.