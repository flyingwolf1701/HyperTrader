# HyperTrader Hedging Strategy Product Requirements Document (PRD)

## 1. Goals and Background Context

### Goals

- To develop a fully automated trading bot that implements the "Advanced Hedging Strategy v6.0.0".
- To capitalize on market volatility in a bull market by taking profits on retracements and compounding gains on recoveries.
- To maintain a long-term upward bias while remaining resilient to significant market drawdowns.
- To build the system on the Hyperliquid platform, leveraging its features for unified positions and high leverage.

### Background Context

This project is based on the "Advanced Hedging Strategy v6.0.0" document. The core thesis is to build a bot for a bull market that is not simply "buy and hold," but actively manages a position through price fluctuations. It uses a dynamic four-phase system (Advance, Retracement, Decline, Recovery) and a crucial reset mechanism. This allows the strategy to systematically lock in profits from volatility and compound them into the base capital for the next trading cycle, aiming for superior risk-adjusted returns.

### Change Log

| Date       | Version | Description                              | Author |
| :--------- | :------ | :--------------------------------------- | :----- |
| 2024-07-31 | 1.0     | Initial draft based on strategy_doc.md v6.0.0 | PM     |

## 2. Requirements

### Functional Requirements

- **FR1: Exchange Integration:** The system must connect to the Hyperliquid exchange using trader-provided credentials (wallet key, private key).
- **FR2: Position Management:** The system must manage a single, unified position for each configured asset, reflecting Hyperliquid's consolidation of orders.
- **FR3: Leverage:** All orders must be placed utilizing the maximum available leverage for the specific asset to maximize capital efficiency.
- **FR4: State Machine:** The system must operate as a state machine, transitioning between four distinct phases: ADVANCE, RETRACEMENT, DECLINE, and RECOVERY.
- **FR5: Unit-Based Tracking:** All strategic actions must be triggered by price movements equivalent to a trader-defined `unit_size`.
- **FR6: ADVANCE Phase Logic:**
  - FR6.1: While 100% long, the system must increment `current_unit` and `peak_unit` as the price rises by `unit_size`.
  - FR6.2: The system must continuously recalculate `position_fragment` as 10% of the growing long position's value.
- **FR7: RETRACEMENT Phase Logic:**
  - FR7.1: The phase must be triggered when the price drops one unit from `peak_unit`.
  - FR7.2: The system must execute the precise sequence of selling long fragments and opening/adding to a short position as defined in the strategy's Retracement table (-1 to -5 units).
  - FR7.3: The system must be able to symmetrically reverse the last action if the price moves back up during this phase.
- **FR8: DECLINE Phase Logic:**
  - FR8.1: The phase must be triggered after the action for -5 units from peak is completed.
  - FR8.2: The system must hold the short and cash positions, updating `valley_unit` to track new lows.
  - FR8.3: The system must calculate `hedge_fragment` (25% of the short position's value) upon signs of price recovery.
- **FR9: RECOVERY Phase Logic:**
  - FR9.1: The phase must be triggered when `current_unit - valley_unit` equals +2.
  - FR9.2: The system must execute the precise sequence of closing short fragments and buying long fragments (with proceeds and cash) as defined in the strategy's Recovery table (+2 to +5 units).
  - FR9.3: The system must be able to symmetrically reverse the last action if the price falls during this phase.
- **FR10: RESET Mechanism:**
  - FR10.1: The mechanism must be triggered when the position becomes 100% long.
  - FR10.2: It must reset all unit-tracking variables (`current_unit`, `peak_unit`, `valley_unit`) to zero.
  - FR10.3: It must update `current_position_allocation` to the new total margin value, effectively compounding the previous cycle's profit/loss.
  - FR10.4: It must re-enter the ADVANCE phase to begin a new cycle.

### Non-Functional Requirements

- **NFR1: Resilience:** The system must be designed to run continuously and handle unexpected market volatility and exchange API errors gracefully (e.g., using retries with exponential backoff).
- **NFR2: State Persistence:** The system's state (current phase, unit counts, etc.) must be persisted to survive application restarts.
- **NFR3: Auditability:** The system must produce structured logs for every state transition, calculation, and trade execution for auditing and debugging purposes.
- **NFR4: Performance:** The system must be performant enough to poll prices and execute trades in a timely manner relative to the `unit_size`.
- **NFR5: Configurability:** Key parameters (`unit_size`, asset to trade, initial allocation) must be easily configurable by the trader.

## 3. User Interface Design Goals

For the initial MVP, this is a headless trading bot. There are no UX/UI requirements. A command-line interface (CLI) for monitoring is specified as a functional requirement in Epic 4. A full graphical user interface (GUI) can be considered as a future project.

## 4. Technical Assumptions

- **Repository Structure:** Monorepo. The application code and tests will reside in a single repository.
- **Service Architecture:** Microservice. The bot will run as a single, long-running process that maintains its own state.
- **Language/Framework:** Python 3, utilizing the `asyncio` library for concurrent operations.
- **Core Libraries:** `ccxt` for exchange interaction.
- **Testing Requirements:** A combination of Unit and Integration tests is required.
  - **Unit Tests:** To verify the logic of the four-phase state machine and fragment calculations in isolation.
  - **Integration Tests:** To verify the connection to the Hyperliquid (testnet) exchange and the correct execution of trade orders.

## 5. Epic List

- **Epic 1: Core Engine & ADVANCE Phase:** Establish the project foundation, connect to Hyperliquid, manage position state, and implement the initial ADVANCE phase logic.
- **Epic 2: RETRACEMENT & DECLINE Phases:** Implement the defensive logic for taking profits during price retracements and managing the position in a downtrend.
- **Epic 3: RECOVERY & RESET Mechanism:** Implement the logic for re-entering a long position during a recovery and the full RESET mechanism to compound profits.
- **Epic 4: Operational Readiness & Monitoring:** Add robust logging, error handling, configuration, and a CLI for monitoring to make the bot deployable.

## 6. Epic Details

### Epic 1: Core Engine & ADVANCE Phase

**Goal:** To build the foundational components of the trading bot, connect to the Hyperliquid exchange, and implement the initial state where the bot manages a fully long position and tracks upward price movements.

- **Story 1.1: Project Setup & Exchange Connection**
  - **As a** developer, **I want** to set up the basic project structure, dependencies, and configuration management, **so that** I can establish a stable connection to the Hyperliquid API.
  - **Acceptance Criteria:**
    1. A project structure with `app`, `tests`, and `config` directories is created.
    2. `ccxt` and other necessary libraries are included in a `requirements.txt` or `pyproject.toml` file.
    3. A configuration module can load API keys, wallet address, and other settings from environment variables.
    4. An exchange service can successfully instantiate the `ccxt` Hyperliquid exchange object.
    5. A health check function can connect to Hyperliquid and fetch the account balance to verify the connection.

- **Story 1.2: Position State Management**
  - **As a** system, **I want** to initialize and track all key strategic variables in a persistent manner, **so that** I can maintain an accurate state for the trading logic across restarts.
  - **Acceptance Criteria:**
    1. A state management class/module is created to hold `unit_size`, `entry_price`, `current_unit`, `peak_unit`, `valley_unit`, etc.
    2. The state can be saved to a local file (e.g., JSON) upon change.
    3. The system can load the last known state from the file on startup.
    4. The system can fetch the current `entry_price` for an asset from the exchange to initialize or validate its state.

- **Story 1.3: Implement ADVANCE Phase Logic**
  - **As a** system, **I want** to monitor the price of a 100% long position and update state variables, **so that** I can track gains and prepare for a potential retracement.
  - **Acceptance Criteria:**
    1. When in the ADVANCE phase, the system polls the current market price for the configured asset.
    2. When the price increases by one `unit_size` above the current `entry_price` plus `current_unit` offset, `current_unit` and `peak_unit` are both incremented by 1.
    3. The `position_fragment` variable is correctly recalculated as 10% of the current total long position's notional value.
    4. The system remains in the ADVANCE phase as long as `current_unit` >= `peak_unit`.

### Epic 2: RETRACEMENT & DECLINE Phases

**Goal:** To implement the defensive and profit-taking logic of the strategy, allowing the bot to systematically reduce long exposure and open short hedges as the price retraces from a peak.

- **Story 2.1: Implement RETRACEMENT Phase Trigger and Scaling Logic**
  - **As a** system, **I want** to detect a price drop from the peak and execute the defined scaling actions, **so that** I can hedge the position and take profits.
  - **Acceptance Criteria:**
    1. The system transitions from ADVANCE to RETRACEMENT when the price drops one unit below `peak_unit`.
    2. For each unit drop from -1 to -4, the system executes the corresponding actions as defined in the RETRACEMENT phase table.
    3. The system correctly calculates and executes the sale of long fragments and the opening/adding to the short position.
    4. The system can reverse each action symmetrically if the price moves back up.

- **Story 2.2: Implement Final RETRACEMENT Step and DECLINE Phase**
  - **As a** system, **I want** to fully exit the long position and enter the DECLINE phase, **so that** I am positioned to profit from a continued downtrend.
  - **Acceptance Criteria:**
    1. At -5 units from peak, the system sells the remaining long position.
    2. The value from the final sale is added to the short position.
    3. The system's state transitions to DECLINE.
    4. In the DECLINE phase, as price falls, `current_unit` is decremented and `valley_unit` is updated to the new low.
    5. If the price starts to recover, `hedge_fragment` is calculated as 25% of the short position's value.

### Epic 3: RECOVERY & RESET Mechanism

**Goal:** To implement the logic that allows the bot to recognize a market recovery, systematically close its hedge, re-establish a long position, and then reset the entire strategy to compound the cycle's gains.

- **Story 3.1: Implement RECOVERY Phase Logic**
  - **As a** system, **I want** to detect a confirmed recovery from the price valley and begin re-allocating to a long position, **so that** I can capture the new uptrend.
  - **Acceptance Criteria:**
    1. The system transitions from DECLINE to RECOVERY when `current_unit - valley_unit` equals +2.
    2. For each unit increase from +2 to +5, the system executes the corresponding actions as defined in the RECOVERY phase table.
    3. This includes closing parts of the short position and using proceeds and cash to buy long.
    4. Actions are reversed symmetrically if the price falls during this phase.

- **Story 3.2: Implement RESET Mechanism**
  - **As a** system, **I want** to reset all strategic variables after a full cycle is complete, **so that** I can lock in profits and begin a new trading cycle with a larger capital base.
  - **Acceptance Criteria:**
    1. The RESET is triggered when the position becomes 100% long (typically after the +6 action in Recovery).
    2. `current_unit`, `peak_unit`, and `valley_unit` are reset to 0.
    3. `current_position_allocation` is updated to the new total margin value of the position.
    4. The system's `entry_price` is updated to reflect the current market price.
    5. The system's state transitions back to the ADVANCE phase.

### Epic 4: Operational Readiness & Monitoring

**Goal:** To make the bot robust, observable, and configurable for real-world deployment.

- **Story 4.1: Implement Structured Logging and Error Handling**
  - **As a** trader, **I want** detailed logs and graceful error handling, **so that** I can audit the bot's behavior and ensure it runs reliably.
  - **Acceptance Criteria:**
    1. A logging library is configured to output structured logs (e.g., JSON) to both console and a rotating file.
    2. Every phase transition, trade order (sent, filled, failed), and state change is logged.
    3. API calls to the exchange are wrapped in try/except blocks that handle network errors with a retry mechanism.

- **Story 4.2: Create a CLI for Monitoring**
  - **As a** trader, **I want** a simple command-line interface to view the bot's current status, **so that** I can monitor its performance without reading raw logs.
  - **Acceptance Criteria:**
    1. A CLI command can be run to display the current state in a clean, readable format.
    2. The display includes: current phase, `current_unit`, `peak_unit`, `valley_unit`, current position composition (long/short/cash %), and overall PNL since last reset.
    3. The CLI includes an option to refresh automatically every N seconds.

## 7. Checklist Results Report

This section will be populated after the PRD is reviewed and the `pm-checklist` is executed.

## 8. Next Steps

- **For the Architect:** Please review this PRD and create a detailed architecture document. Pay close attention to the state machine implementation, state persistence, and the interaction with the `ccxt` library for trade execution.

Please review the document. We can now move forward to the architect for system design, or we can iterate on this PRD if you have any changes.

<!--
[PROMPT_SUGGESTION]@architect please create the architecture document based on the new PRD.[/PROMPT_SUGGESTION]
[PROMPT_SUGGESTION]Let's refine the stories in Epic 1 to be more granular.[/PROMPT_SUGGESTION]
