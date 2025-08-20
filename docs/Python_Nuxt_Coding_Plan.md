# HyperTrader Coding Plan - Python & Nuxt Implementation

> **Complete technical implementation guide for the HyperTrader application**

This document provides a comprehensive coding plan for the HyperTrader application, covering the backend API, core trading logic, and frontend user interface. The implementation uses Python/FastAPI for the backend and Nuxt.js/TypeScript for the frontend.

---

## 📋 Table of Contents

- [1. Project File Structure](#1-project-file-structure)
- [2. Backend Plan (Python & FastAPI)](#2-backend-plan-python--fastapi)
- [3. Frontend Plan (Nuxt & TypeScript)](#3-frontend-plan-nuxt--typescript)
- [4. Testing Strategy](#4-testing-strategy)

---

## 1. Project File Structure

### Overview

A clean, modular structure with integrated testing is essential for maintainability and scalability. The project follows a monorepo structure with separate backend and frontend directories.

### Directory Structure
```
hypertrader/
├── backend/              # FastAPI Project
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py         # FastAPI app entry point
│   │   ├── api/            # API endpoints
│   │   │   ├── __init__.py
│   │   │   ├── endpoints.py  # REST endpoints
│   │   │   └── websockets.py # WebSocket endpoint
│   │   ├── core/           # Configuration, settings
│   │   │   └── config.py
│   │   ├── db/             # Database connection (Neon/PostgreSQL)
│   │   │   ├── __init__.py
│   │   │   └── session.py
│   │   ├── models/         # Pydantic models for data validation
│   │   │   └── state.py      # SystemState model
│   │   ├── schemas/        # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── favorite.py
│   │   │   └── plan.py
│   │   └── services/       # Business logic
│   │       ├── __init__.py
│   │       ├── exchange.py   # CCXT integration
│   │       └── trading_logic.py # All phase handlers
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── contract/       # Pact contract tests
│   │   ├── integration/    # Tests involving DB or external services
│   │   └── unit/           # Unit tests for services and logic
│   ├── .env
│   └── pyproject.toml
│
└── frontend/             # Nuxt 3 Project
    ├── app.vue             # Main layout component
    ├── nuxt.config.ts      # Nuxt configuration
    ├── package.json
    ├── tsconfig.json
    ├── assets/             # CSS, images, fonts
    │   └── css/
    │       └── main.css
    ├── components/         # Reusable Vue components
    │   ├── AllocationDisplay.vue
    │   ├── Dashboard.vue
    │   └── StatusIndicator.vue
    ├── composables/        # Reusable state logic
    │   ├── useSystemState.ts
    │   └── useWebSocket.ts
    ├── layouts/            # Page layouts
    │   └── default.vue
    ├── pages/              # Application routes
    │   ├── index.vue
    │   ├── pairs.vue
    │   └── trade/
    │       └── new.vue
    ├── server/             # Server-side routes/middleware
    │   └── api/
    └── tests/
        ├── contract/       # Pact contract tests
        └── unit/           # Vitest unit/component tests
```

## 2. Backend Plan (Python & FastAPI)

### Overview

The backend serves as the core engine of the HyperTrader application. It manages:
- Trading logic execution
- Exchange connectivity
- Real-time data streaming
- API endpoints for the frontend
- Database operations

### Architecture Components

### A. Core Data Structure (`/models/state.py`)

**Purpose**: Define the SystemState class using Pydantic's BaseModel for data validation and serialization.

#### Critical Requirements

> ⚠️ **Important**: All fields representing prices or dollar amounts must use Python's `Decimal` type for high-precision calculations.

```python
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional

class SystemState(BaseModel):
    symbol: str
    current_phase: str
    entry_price: Decimal
    unit_value: Decimal
    # ... other fields
```

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Trading pair (e.g., "BTC/USDT") |
| `current_phase` | `str` | Current trading phase |
| `entry_price` | `Decimal` | Initial average fill price |
| `unit_value` | `Decimal` | Dollar value per unit movement |
| `long_invested` | `Decimal` | Long allocation investment |
| `hedge_short` | `Decimal` | Hedge allocation short position |

### B. Database Layer (`/db/session.py`)

#### Technology Stack
- **ORM**: SQLAlchemy 2.0 with async support
- **Driver**: `asyncpg` for PostgreSQL connectivity
- **Database**: Neon PostgreSQL

#### Responsibilities

```python
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

class DatabaseManager:
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url)
        self.session_maker = async_sessionmaker(self.engine)
    
    async def get_session(self):
        # Dependency injection for FastAPI
        pass
```

#### Key Functions

| Function | Purpose |
|----------|----------|
| `get_session()` | Provides async database sessions |
| `persist_state()` | Saves SystemState to `trading_plans` table |
| `manage_favorites()` | Handles `user_favorites` table operations |

### C. Exchange Service (`/services/exchange.py`)

#### Purpose
Wrapper around the CCXT library for exchange interactions with robust error handling and rate limiting.

#### Implementation

```python
import ccxt.async_support as ccxt
from typing import Dict, Any

class ExchangeManager:
    def __init__(self, api_key: str, secret: str):
        self.exchange = ccxt.hyperliquid({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,  # Critical for API compliance
            'sandbox': False  # Set to True for testing
        })
    
    async def place_order(self, symbol: str, order_type: str, 
                         side: str, amount: float) -> Dict[str, Any]:
        # Implementation with error handling
        pass
```

#### Required Async Methods

| Method | Parameters | Returns | Purpose |
|--------|------------|---------|----------|
| `place_order()` | symbol, type, side, amount | Order result | Execute trades |
| `get_current_price()` | symbol | Current price | Real-time pricing |
| `fetch_markets()` | None | Available markets | Market discovery |
| `get_balance()` | None | Account balance | Portfolio tracking |

### D. Trading Logic (`/services/trading_logic.py`)
This module contains the core decision-making engine of the trading bot. It implements the four-phase system logic.

**Key Functions**:
- `OnUnitChange(state: SystemState)`: The central "traffic cop" function. It determines the current phase based on the state and calls the appropriate handler.
- **Phase Handlers**:
  - `handleAdvancePhase`
  - `handleRetracementPhase`
  - `handleDeclinePhase`
  - `handleRecoveryPhase`
- `performSystemReset(state: SystemState)`: Called when reset conditions are met (`longCash == 0` and `hedgeShort == 0`)

### E. WebSocket & Main Loop (`/api/websockets.py`)
Use FastAPI's WebSocket support to create an endpoint like `/ws/{symbol}`.

**Main Loop Logic**:
1. Connect to the exchange's WebSocket
2. On each price tick, trigger the `OnUnitChange` handler
3. After logic runs, broadcast updated SystemState to all connected frontend clients

### F. REST API (`/api/endpoints.py`)
Create standard REST endpoints for the frontend to interact with the bot:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/trade/start` | Start a new trade |
| GET | `/trade/state/{symbol}` | Get current trade state |
| GET | `/exchange/pairs` | List available trading pairs |
| GET | `/user/favorites` | Get user's favorite pairs |
| POST | `/user/favorites` | Add/remove favorite pairs |

## 3. Frontend Plan (Nuxt & TypeScript)

### Overview

The frontend serves as the command center, providing:
- Real-time trading status visualization
- Portfolio performance monitoring
- Trade management interface
- System configuration controls

### Technology Stack

- **Framework**: Nuxt 3 with TypeScript
- **Styling**: Tailwind CSS (recommended)
- **State Management**: Nuxt built-in `useState`
- **WebSocket**: Native WebSocket API
- **Testing**: Vitest for unit/component tests

### A. State Management (`/composables/useSystemState.ts`)

#### Purpose
Manages global application state using Nuxt's reactive state management.

#### Implementation

```typescript
interface SystemState {
  symbol: string;
  currentPhase: string;
  entryPrice: number;
  unitValue: number;
  longInvested: number;
  hedgeShort: number;
  // ... other fields matching Pydantic model
}

export const useSystemState = () => {
  const state = useState<SystemState | null>('systemState', () => null);
  
  const updateState = (newState: SystemState) => {
    state.value = newState;
  };
  
  return {
    state: readonly(state),
    updateState
  };
};
```

#### Key Features

- **Type Safety**: TypeScript interfaces match backend models
- **Reactivity**: Automatic UI updates on state changes
- **Immutability**: State updates through controlled methods

### B. WebSocket Service (`/composables/useWebSocket.ts`)

#### Purpose
Manages real-time communication with the FastAPI backend via WebSocket connections.

#### Implementation

```typescript
export const useWebSocket = () => {
  const { updateState } = useSystemState();
  let socket: WebSocket | null = null;
  
  const connect = (symbol: string) => {
    const wsUrl = `ws://localhost:8000/ws/${symbol}`;
    socket = new WebSocket(wsUrl);
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      updateState(data);
    };
    
    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  };
  
  const disconnect = () => {
    socket?.close();
    socket = null;
  };
  
  return { connect, disconnect };
};
```

#### Features

- **Auto-reconnection**: Handles connection drops
- **Error Handling**: Robust error management
- **State Integration**: Automatic state updates

### C. Components (`/components/`)

#### Component Architecture
Break the UI into small, reusable, and testable components:

| Component | Purpose | Props |
|-----------|---------|-------|
| `Dashboard.vue` | Main trading dashboard | `systemState` |
| `StatusIndicator.vue` | Phase and status display | `phase`, `status` |
| `AllocationDisplay.vue` | Portfolio allocation view | `allocations` |
| `PnLTracker.vue` | Profit/loss visualization | `pnlData` |
| `TradingChart.vue` | Price chart with indicators | `priceData`, `trades` |
| `ControlPanel.vue` | Manual control interface | `onStart`, `onStop` |

#### Component Standards

```vue
<template>
  <div class="component-wrapper">
    <!-- Clean, semantic HTML -->
  </div>
</template>

<script setup lang="ts">
// TypeScript with composition API
interface Props {
  // Well-defined prop types
}

defineProps<Props>();
</script>

<style scoped>
/* Scoped styles with Tailwind classes */
</style>
```

### D. Pages (`/pages/`)

#### Page Structure

| Page | Route | Purpose | Key Features |
|------|-------|---------|-------------|
| `index.vue` | `/` | Main dashboard | Real-time data, WebSocket connection |
| `trade/new.vue` | `/trade/new` | Start new trades | Form validation, favorite pairs |
| `pairs.vue` | `/pairs` | Manage trading pairs | CRUD operations, favorites |
| `settings.vue` | `/settings` | Configuration | API keys, preferences |

#### Page Implementation Example

```vue
<!-- pages/index.vue -->
<template>
  <div class="dashboard-container">
    <Dashboard :system-state="state" />
    <AllocationDisplay :allocations="allocations" />
    <StatusIndicator :phase="state?.currentPhase" />
  </div>
</template>

<script setup lang="ts">
const { state } = useSystemState();
const { connect } = useWebSocket();

// Connect to WebSocket on mount
onMounted(() => {
  if (state.value?.symbol) {
    connect(state.value.symbol);
  }
});

const allocations = computed(() => ({
  longInvested: state.value?.longInvested || 0,
  hedgeShort: state.value?.hedgeShort || 0
}));
</script>
```

## 4. Testing Strategy

### Overview

A comprehensive, multi-layered testing approach ensuring reliability, maintainability, and high code coverage across the entire application stack.

### Testing Pyramid

```
    ┌─────────────────┐
    │   E2E Tests     │  ← Minimal, critical user journeys
    │   (Playwright)  │
    ├─────────────────┤
    │ Integration     │  ← API + DB interactions
    │ Tests (pytest)  │
    ├─────────────────┤
    │   Unit Tests    │  ← Core logic, components
    │ (pytest/vitest) │  ← Largest test suite
    └─────────────────┘
```

### A. Backend Testing (pytest)

#### Unit Tests (`/tests/unit/`)

**Focus Areas**:
- Trading logic validation
- Exchange service functionality
- Database operations
- API endpoint behavior

**Key Testing Libraries**:

```python
# requirements-test.txt
pytest>=7.0.0
pytest-asyncio>=0.21.0
hypothesis>=6.0.0
pytest-mock>=3.10.0
```

**Example Test Structure**:

```python
# tests/unit/test_trading_logic.py
import pytest
from hypothesis import given, strategies as st
from decimal import Decimal

from app.services.trading_logic import OnUnitChange
from app.models.state import SystemState

class TestTradingLogic:
    @given(
        current_unit=st.integers(-10, 10),
        long_invested=st.decimals(min_value=0, max_value=10000)
    )
    def test_phase_transitions(self, current_unit, long_invested):
        # Property-based testing with Hypothesis
        state = SystemState(
            current_unit=current_unit,
            long_invested=long_invested,
            # ... other fields
        )
        result = OnUnitChange(state)
        assert result.current_phase in ['advance', 'retracement', 'decline', 'recovery']
```

#### Integration Tests (`/tests/integration/`)

**Test Scenarios**:

| Test Category | Description | Tools |
|---------------|-------------|-------|
| API Integration | Full request/response cycles | FastAPI TestClient |
| Database Integration | ORM operations with test DB | SQLAlchemy + pytest fixtures |
| Exchange Integration | CCXT mock interactions | pytest-mock |
| WebSocket Integration | Real-time data flow | WebSocket test client |

### B. Frontend Testing (Vitest)

#### Unit & Component Tests (`/tests/unit/`)

**Testing Scope**:
- Composable functions
- Vue component rendering
- User interactions
- State management

**Configuration**:

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'happy-dom',
    coverage: {
      reporter: ['text', 'html'],
      threshold: {
        global: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80
        }
      }
    }
  }
})
```

#### Test Examples

```typescript
// tests/unit/composables/useSystemState.test.ts
import { describe, it, expect } from 'vitest'
import { useSystemState } from '~/composables/useSystemState'

describe('useSystemState', () => {
  it('should update state correctly', () => {
    const { state, updateState } = useSystemState()
    const mockState = {
      symbol: 'BTC/USDT',
      currentPhase: 'advance',
      entryPrice: 50000
    }
    
    updateState(mockState)
    expect(state.value).toEqual(mockState)
  })
})
```

```typescript
// tests/unit/components/StatusIndicator.test.ts
import { mount } from '@vue/test-utils'
import StatusIndicator from '~/components/StatusIndicator.vue'

describe('StatusIndicator', () => {
  it('renders advance phase correctly', () => {
    const wrapper = mount(StatusIndicator, {
      props: {
        phase: 'advance',
        status: 'active'
      }
    })
    
    expect(wrapper.text()).toContain('ADVANCE')
    expect(wrapper.classes()).toContain('status-active')
  })
})
```

### C. Contract Testing (Pact)

#### Purpose
Ensures API compatibility between frontend and backend without requiring full end-to-end tests.

#### Frontend Contract Definition (`/tests/contract/`)

```typescript
// tests/contract/exchange-api.pact.test.ts
import { PactV3, MatchersV3 } from '@pact-foundation/pact'

const provider = new PactV3({
  consumer: 'HyperTrader-Frontend',
  provider: 'HyperTrader-Backend'
})

describe('Exchange API Contract', () => {
  it('should return trading pairs', async () => {
    await provider
      .given('trading pairs exist')
      .uponReceiving('a request for trading pairs')
      .withRequest({
        method: 'GET',
        path: '/exchange/pairs'
      })
      .willRespondWith({
        status: 200,
        headers: {
          'Content-Type': 'application/json'
        },
        body: MatchersV3.eachLike({
          symbol: MatchersV3.string('BTC/USDT'),
          baseAsset: MatchersV3.string('BTC'),
          quoteAsset: MatchersV3.string('USDT')
        })
      })
      .executeTest(async (mockServer) => {
        // Test implementation
        const response = await fetch(`${mockServer.url}/exchange/pairs`)
        expect(response.status).toBe(200)
      })
  })
})
```

#### Backend Contract Verification (`/tests/contract/`)

```python
# tests/contract/test_pact_verification.py
import pytest
from pact import Verifier

def test_pact_verification():
    verifier = Verifier(
        provider='HyperTrader-Backend',
        provider_base_url='http://localhost:8000'
    )
    
    success, logs = verifier.verify_pacts(
        './pacts/hypertrader-frontend-hypertrader-backend.json'
    )
    
    assert success
```

#### Benefits

- **Early Detection**: API breaking changes caught in development
- **Documentation**: Living documentation of API contracts
- **Confidence**: Safe refactoring of backend/frontend independently
- **Efficiency**: Faster than full E2E tests

---

## Summary

This comprehensive coding plan provides the complete technical architecture for implementing the HyperTrader application. The modular design ensures:

### Key Benefits

- **Scalability**: Microservices-ready architecture
- **Maintainability**: Clean separation of concerns
- **Reliability**: Comprehensive testing strategy
- **Performance**: Async/await patterns throughout
- **Type Safety**: Full TypeScript integration

### Next Steps

1. Set up the project structure
2. Implement backend core services
3. Develop frontend components
4. Establish testing frameworks
5. Deploy and monitor

---

**Technologies**: Python 3.11+ • FastAPI • Nuxt 3 • TypeScript • PostgreSQL • WebSockets • CCXT

*Last updated: 2025-08-20*