HyperTrader - Product Development Plan
1. Project Overview
Product: HyperTrader Backend Engine
Goal: To implement the "Advanced Hedging Strategy v6.0.0" as a Python-based automated trading application that interacts with the Hyperliquid exchange.
Core Functionality: The application will manage a unified long/short/cash position for multiple crypto assets, executing trades automatically based on a four-phase system driven by pre-defined price "unit" movements.

2. Technical Stack & Architecture
Language: Python

Package Manager: UV

Exchange Interaction: ccxt library for placing orders and fetching account data.

Real-Time Data: websockets library for a persistent connection to the Hyperliquid API to receive live price feeds.

Environment: Backend service architecture.

3. Development Roadmap & Sprints
Stage 1: WebSocket Connection & Price Logging
Objective: Establish a stable, real-time connection to Hyperliquid's WebSocket API and reliably log price data for a target asset (e.g., Ethereum).

Key Tasks:

Initialize the Python project environment using UV.

Install required packages: websockets, asyncio, ccxt.

Develop a script to connect to the Hyperliquid WebSocket endpoint (wss://api.hyperliquid.xyz/ws).

Implement logic to subscribe to the trades or l2Book channel for the desired asset (e.g., {"method": "subscribe", "subscription": {"type": "trades", "coin": "ETH"}}).

Write a message handler to parse incoming JSON data and extract the current price.

Implement a simple console logger that timestamps and prints the received price.

Testing & Acceptance Criteria:

Test Case: Run the WebSocket listener script.

Expected Outcome: The console continuously displays a stream of timestamped prices for ETH without errors or disconnections for at least 10 minutes.

Example Log: [2025-08-24 21:45:10] ETH Price: $3450.25

Stage 2: Unit Change Tracking
Objective: Create a function that processes the raw price feed and translates it into discrete "unit" changes as defined by the strategy.

Key Tasks:

Design a state management class or dictionary to hold key strategy variables (entry_price, unit_size, current_unit).

Create a core function, calculate_unit_change(current_price), that is called by the WebSocket listener.

Inside this function, calculate the price delta (current_price - entry_price).

Determine if the delta has crossed a full unit_size threshold (either positive or negative).

If a unit change is detected, update the current_unit state variable and log the change.

Testing & Acceptance Criteria:

Test Case 1 (Upward Unit Change):

Setup: entry_price = $3450.00, unit_size = $2.00, current_unit = 0.

Input: Simulate receiving a current_price of $3452.50.

Expected Outcome: current_unit is updated to 1. A log message is generated: Unit change: 0 -> 1.

Test Case 2 (Downward Unit Change):

Setup: entry_price = $3450.00, unit_size = $2.00, current_unit = 0.

Input: Simulate receiving a current_price of $3447.50.

Expected Outcome: current_unit is updated to -1. A log message is generated: Unit change: 0 -> -1.

Test Case 3 (No Change):

Setup: entry_price = $3450.00, unit_size = $2.00, current_unit = 0.

Input: Simulate receiving a current_price of $3451.50.

Expected Outcome: current_unit remains 0. No unit change is logged.

Stage 3: CCXT Exchange Integration & Validation
Objective: Develop and validate all necessary functions for reading account data and executing market orders on Hyperliquid via ccxt.

Key Tasks:

Write a module to handle the ccxt exchange connection, including API key authentication.

Create wrapper functions for all required actions:

get_position(symbol): Fetches current long/short position details.

get_balance(currency): Fetches available cash/margin.

place_market_order(symbol, side, amount): A single function to handle buy (long) and sell (short or close long).

close_position(symbol): A specific function to fully close an existing position.

Testing & Acceptance Criteria:

Acceptance: All wrapper functions are tested manually against the Hyperliquid (testnet or mainnet) account using a script or curl commands, and their outcomes are verified directly on the exchange interface.

Test Case (Long Order):

Action: Execute place_market_order('ETH/USDC:USDC', 'buy', 0.01).

Verification: A 0.01 ETH long position appears in the Hyperliquid account.

Test Case (Short Order):

Action: Execute place_market_order('ETH/USDC:USDC', 'sell', 0.01).

Verification: A 0.01 ETH short position appears in the Hyperliquid account.

Test Case (Fetch Data):

Action: Execute get_position('ETH/USDC:USDC').

Verification: The script prints accurate details of the existing ETH position.

Stage 4: "Enter Trade" & ADVANCE Phase Implementation
Objective: Automate the initial trade entry process and correctly establish the ADVANCE phase state.

Key Tasks:

Create the main start_trade(symbol, initial_margin, unit_size) function.

This function will call the place_market_order function to open a 100% long position based on the initial_margin and the asset's max leverage.

After the order fills, fetch the position's entry_price from the exchange.

Initialize all strategy state variables: phase = 'ADVANCE', current_unit = 0, peak_unit = 0, valley_unit = 0.

Connect the unit tracking logic to the live WebSocket feed.

Testing & Acceptance Criteria:

Test Case: Execute start_trade('ETH/USDC:USDC', 100, 2).

Expected Outcome:

A long position is successfully opened on Hyperliquid.

The application's internal state is correctly set to the ADVANCE phase with units at 0.

The WebSocket listener begins tracking unit changes from the confirmed entry_price.

Stage 5: RETRACEMENT Phase Implementation
Objective: Implement the complete logic for the RETRACEMENT phase, including scaling out of longs and into shorts, and handling reversals.

Key Tasks:

Enhance the main loop to update peak_unit whenever a new high is made in the ADVANCE phase.

Continuously calculate position_fragment (10% of the current long position's value).

Implement a condition that changes the phase to RETRACEMENT when current_unit - peak_unit becomes -1.

Create a handle_retracement() function that uses a match/case or if/elif structure to execute the precise trades outlined in the strategy for units -1 through -5.

Build the reversal logic to undo trades if the unit count moves back toward the peak.

Testing & Acceptance Criteria:

Test Case (Enter Retracement):

Setup: ADVANCE phase, peak_unit = 3.

Input: Simulate price drop causing current_unit to become 2 (units_from_peak = -1).

Expected Outcome: The app correctly sells 1 position_fragment and shorts 1 position_fragment. The phase variable changes to RETRACEMENT.

Test Case (Full Retracement & Reversal):

Setup: RETRACEMENT phase, units_from_peak = -3.

Input: Simulate price drop to units_from_peak = -4, then a recovery to units_from_peak = -3.

Expected Outcome: The app first executes the sell/short orders for the -4 level, then correctly executes the buy/cover orders to return to the -3 portfolio state.

Stage 6: RESET Mechanism Implementation
Objective: Create the logic to reset the strategy's state variables after a full cycle is complete.

Key Tasks:

Develop a check_for_reset() function.

This function will be called after any trade that could result in a 100% long position (i.e., during the RECOVERY phase).

The function checks two conditions: (1) short position size is 0, and (2) cash balance is near 0.

If true, it triggers the reset process: resets all unit variables to 0, updates current_position_allocation with the new total margin, and sets phase = 'ADVANCE'.

Testing & Acceptance Criteria:

Test Case: Manually set the application state to be in the RECOVERY phase, 90% long with a small remaining short and cash position. Simulate the final buy/cover trade that makes the position 100% long.

Expected Outcome: The check_for_reset() function is triggered. A log message "RESET TRIGGERED" is displayed. All unit variables in the state are reset to 0, and the phase is set back to ADVANCE.

Stage 7: DECLINE Phase Implementation
Objective: Implement the logic for the DECLINE phase, where the system holds a defensive position and tracks new lows.

Key Tasks:

In the handle_retracement logic, add the state transition to phase = 'DECLINE' once the actions for unit -5 are complete.

Create a handle_decline() function.

In this function, as price falls, update valley_unit to match current_unit.

If price begins to recover, calculate and store hedge_fragment (25% of the short position's value).

Testing & Acceptance Criteria:

Test Case: Force the system into the DECLINE phase state (units_from_peak < -5).

Input: Simulate a continued price drop.

Expected Outcome: No trades are executed. The valley_unit variable is continuously updated to the new lowest current_unit.

Stage 8: RECOVERY Phase Implementation
Objective: Automate the systematic re-entry into a long position from a market bottom.

Key Tasks:

In the main loop, add a condition to transition from DECLINE to RECOVERY when current_unit - valley_unit equals 2.

Create a handle_recovery() function.

Implement the match/case or if/elif logic to execute the specific buy/cover trades for units +2 through +5, using the calculated hedge_fragment and position_fragment.

Ensure that after the final recovery step, the check_for_reset() function is called, leading back to the ADVANCE phase.

Testing & Acceptance Criteria:

Test Case (Full Recovery Cycle):

Setup: DECLINE phase, valley_unit = -15.

Input: Simulate a price recovery where current_unit increments from -14 up to -9.

Expected Outcome: The phase correctly transitions to RECOVERY at current_unit = -13. The app executes the precise sequence of buy/cover orders at units +2, +3, +4, and +5. Upon reaching 100% long, the RESET mechanism is triggered successfully.