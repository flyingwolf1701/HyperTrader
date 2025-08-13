# HyperTrader Project Knowledge Base

## Project Overview
**HyperTrader** - Personal Fibonacci hedging trading assistant that automates position management and order execution based on pre-defined trading plans. Designed to capture 77% of upward moves while limiting downside to 23% through intelligent hedging.

## Current Tech Stack

### Frontend (Nuxt 4)
- **Framework**: Nuxt 4.0.3 with Vue 3 Composition API
- **State Management**: Pinia
- **Styling**: CSS + SCSS
- **Package Manager**: Bun
- **Port**: 3001
- **Authentication**: None (local development only)

### Backend (Python + FastAPI)
- **Framework**: FastAPI with async Python
- **Language**: Python 3.11+
- **Package Manager**: uv
- **Linter**: ruff
- **Database**: Neon PostgreSQL using asyncpg
- **Trading Integration**: ccxt for REST API calls to HyperLiquid
- **Market Data**: Custom WebSocket connection to HyperLiquid feeds
- **Port**: 3000

### Key Libraries
- **FastAPI**: Modern async Python web framework
- **CCXT**: Unified cryptocurrency exchange API for order execution
- **WebSockets**: Direct HyperLiquid WebSocket connection for real-time data
- **asyncpg**: Async PostgreSQL driver
- **Pydantic**: Data validation and settings management
- **NumPy/Pandas**: Mathematical calculations for Fibonacci levels

## Project Structure
```
hyper_trader/
├── frontend/                 # Nuxt 4 app (runs on :3001)
│   └── app/                  # Modern Nuxt 4 app directory structure
│       ├── pages/
│       │   ├── index.vue           # Dashboard overview
│       │   ├── plans/
│       │   │   ├── create.vue      # Trading plan creation
│       │   │   ├── index.vue       # Plans list
│       │   │   └── [id].vue        # Individual plan monitoring
│       │   ├── portfolio/
│       │   │   ├── index.vue       # Portfolio allocation management
│       │   │   └── settings.vue    # Cash/spot savings configuration
│       │   └── logs.vue            # Execution history
│       ├── components/
│       │   ├── FibonacciCalculator.vue
│       │   ├── PositionManager.vue
│       │   ├── PortfolioAllocator.vue
│       │   └── OrderBook.vue
│       ├── composables/
│       │   ├── useTradingPlan.ts
│       │   ├── usePortfolio.ts
│       │   └── useMarketData.ts
│       └── app.vue               # Root app component
├── backend/                  # Python FastAPI (runs on :3000)
│   ├── src/
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── api/
│   │   │   ├── trading_plans.py    # CRUD for trading plans
│   │   │   ├── portfolio.py        # Portfolio management endpoints
│   │   │   ├── positions.py        # Active position monitoring
│   │   │   └── market_data.py      # WebSocket market data endpoints
│   │   ├── services/
│   │   │   ├── hyperliquid_client.py    # CCXT HyperLiquid integration
│   │   │   ├── websocket_manager.py     # Custom WebSocket handler
│   │   │   ├── execution_engine.py      # Trading logic execution
│   │   │   └── portfolio_manager.py     # Portfolio allocation logic
│   │   ├── calculators/
│   │   │   ├── fibonacci.py        # Position-relative Fibonacci levels
│   │   │   ├── position_sizing.py  # Risk management calculations
│   │   │   └── stop_loss.py        # Dynamic stop loss logic
│   │   ├── models/
│   │   │   ├── trading_plan.py     # Trading plan data models
│   │   │   ├── position.py         # Position tracking models
│   │   │   └── portfolio.py        # Portfolio allocation models
│   │   └── database/
│   │       ├── connection.py       # PostgreSQL connection
│   │       ├── migrations/         # Database schema migrations
│   │       └── repositories/       # Data access layer
│   ├── pyproject.toml             # uv package configuration
│   └── ruff.toml                  # Linting configuration
├── docs/
│   └── trading_strategy.md        # Fibonacci hedging strategy document
├── README.md
└── .gitignore
```

## What's Implemented ✅

### Basic Infrastructure
- **Frontend Structure**: Nuxt 4 app with modern directory structure
- **Backend Foundation**: FastAPI application setup ready
- **Database**: Neon PostgreSQL connection established
- **Development Tools**: uv and ruff configured for Python development
- **CORS**: Properly configured between frontend/backend

## What's NOT Implemented Yet ❌

### Core Trading Features
- [ ] Trading plan creation and management interface
- [ ] Position-relative Fibonacci calculation engine
- [ ] HyperLiquid WebSocket integration for real-time price feeds
- [ ] CCXT integration for order execution
- [ ] Dynamic hedging system (23% pullback triggers)
- [ ] Position scaling logic (38% and 50% retracement levels)
- [ ] Automatic stop loss management with trailing functionality

### Portfolio Management
- [ ] Multi-position portfolio allocation system
- [ ] Cash reserve management (configurable percentage)
- [ ] Spot savings feature for long-term accumulation
- [ ] Portfolio rebalancing and graceful position exits
- [ ] Profit processing with automatic cash/spot allocation

### Frontend Components
- [ ] Trading plan creation form with Fibonacci parameter input
- [ ] Real-time position monitoring dashboard
- [ ] Portfolio allocation management interface
- [ ] Market data visualization components
- [ ] Execution history and logging display
- [ ] Configuration panels for risk management settings

### Database Schema
- [ ] Trading plans table with Fibonacci parameters
- [ ] Positions tracking with entry/exit history
- [ ] Portfolio allocations and settings
- [ ] Execution logs for all trades and decisions
- [ ] Spot savings accumulation records
- [ ] Market data caching for performance

### Trading Engine
- [ ] Real-time market monitoring via WebSocket
- [ ] Automated hedge execution at 23% retracement
- [ ] Position scaling at 38% and 50% levels
- [ ] Dynamic stop loss adjustment system
- [ ] Short position management with configurable stops
- [ ] Trend analysis and fractal reset logic

### Risk Management
- [ ] Maximum drawdown controls (23% cap)
- [ ] Position size limits and leverage controls
- [ ] User-configurable risk parameters
- [ ] Emergency stop and manual override system
- [ ] Portfolio-wide risk monitoring

## Technical Architecture

### Market Data Flow
- **WebSocket Connection**: Direct connection to HyperLiquid for real-time price feeds
- **Data Processing**: Real-time calculation of position-relative Fibonacci levels
- **Event Triggers**: Automated detection of retracement thresholds
- **Order Execution**: CCXT-based REST API calls for position management

### Position Management System
- **Entry Tracking**: Monitor position high since entry (not historical highs)
- **Retracement Calculation**: 23%, 38%, 50% pullbacks based on position gains
- **Hedge Logic**: Automatic 50%/50% long/short split at 23% retracement
- **Scaling Logic**: Progressive position reduction at deeper retracement levels
- **Stop Management**: Dynamic trailing stops with user-configurable parameters

### Portfolio Architecture
- **Multi-Position Support**: 1-20 concurrent positions with individual management
- **Allocation Control**: User-defined percentage allocation per coin
- **Cash Management**: Automatic reserve maintenance through profit skimming
- **Spot Savings**: Forced long-term accumulation separate from trading portfolio
- **Rebalancing**: Manual and automatic portfolio rebalancing capabilities

## Database Schema Requirements

### Core Tables
- **trading_plans**: Strategy parameters, Fibonacci levels, risk settings
- **positions**: Active and historical position tracking
- **portfolio_allocations**: Coin allocation percentages and targets
- **execution_logs**: Complete audit trail of all trading decisions
- **spot_savings**: Long-term accumulation tracking
- **market_data_cache**: Recent price history for calculations

### Key Relationships
- **Plans to Positions**: One-to-many (plan can have multiple position entries)
- **Portfolio to Plans**: Many-to-many (allocation affects multiple plans)
- **Positions to Logs**: One-to-many (detailed execution history per position)

## Development Roadmap

### Phase 1: Core Infrastructure
- Set up Python backend with FastAPI and uv package management
- Implement PostgreSQL database schema and migrations
- Create basic trading plan data models and API endpoints
- Establish HyperLiquid WebSocket connection for market data

### Phase 2: Fibonacci Calculation Engine
- Implement position-relative Fibonacci level calculations
- Build real-time price monitoring and retracement detection
- Create automated hedge trigger system (23% pullback)
- Develop dynamic stop loss management

### Phase 3: Trading Execution
- Integrate CCXT for HyperLiquid order execution
- Implement automated hedge execution (sell 50% + short 50%)
- Build position scaling logic for 38% and 50% retracements
- Add manual override and emergency stop functionality

### Phase 4: Portfolio Management
- Create multi-position portfolio allocation system
- Implement cash reserve management with configurable targets
- Build spot savings feature for long-term accumulation
- Add portfolio rebalancing and position exit capabilities

### Phase 5: Frontend Interface
- Design and build trading plan creation interface
- Create real-time position monitoring dashboard
- Implement portfolio allocation management UI
- Build execution history and performance analytics

### Phase 6: Advanced Features
- Add trend analysis and fractal reset logic
- Implement advanced risk management controls
- Create performance analytics and strategy optimization
- Build mobile-responsive interface for monitoring

### Phase 7: Production Readiness
- Implement comprehensive error handling and recovery
- Add extensive logging and monitoring capabilities
- Create backup and disaster recovery procedures
- Optimize performance for high-frequency market data

## Strategy Implementation Notes

### Position-Relative Fibonacci System
- All calculations based on position entry price and highest point reached
- Retracements measured as percentages of unrealized gains, not absolute price
- Dynamic recalculation as new highs are established
- Automatic reset when taking profits and re-entering positions

### Risk Management Philosophy
- Maximum 23% drawdown from any position peak
- Capture 77% of upward moves through systematic hedging
- Never attempt to time exact peaks or bottoms
- Maintain long bias in bull markets with short hedges for protection

### Portfolio Allocation Strategy
- Support single coin focus or diversified multi-coin approach
- Local compounding within individual coin allocations
- Graceful exit capability for underperforming positions
- Automatic cash and spot savings management

## Current State Summary
- ✅ **Project Vision**: Clear strategy and technical requirements defined
- ✅ **Architecture**: Modern tech stack selected (Python/FastAPI + Nuxt 4)
- ❌ **Implementation**: Core trading features need development
- ❌ **Integration**: HyperLiquid WebSocket and CCXT integration pending
- ❌ **UI**: Trading interface components need creation
- ❌ **Database**: Schema design and implementation required

The project is positioned to begin core development of the Fibonacci hedging trading system with a clear roadmap from infrastructure to advanced portfolio management features.