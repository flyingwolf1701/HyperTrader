# HyperTrader Frontend

Professional real-time trading dashboard for the HyperTrader 4-phase hedging strategy. Built with Nuxt 3, Vue 3, and TypeScript for responsive, real-time visualization of automated crypto trading operations.

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ or Bun
- HyperTrader Backend running on `http://localhost:3000`

### Installation

```bash
# Install dependencies
bun install
# or npm install

# Start development server
bun dev
# or npm run dev
```

The frontend will be available at `http://localhost:3001`

## 🎯 Features

### Real-Time Trading Dashboard
- **Live price feeds** via WebSocket connection
- **4-phase strategy visualization** with current phase indicators
- **Portfolio allocation tracking** with interactive charts
- **Profit/Loss monitoring** with real-time calculations
- **System status indicators** showing connection health

### Trading Management
- **Create new trading plans** with intuitive forms
- **Monitor active strategies** across multiple symbols
- **Emergency controls** for stopping/starting trades
- **Historical performance** tracking and analysis

### Market Data
- **Browse available trading pairs** from HyperLiquid
- **Favorite pairs management** for quick access
- **Real-time price updates** for all markets
- **Market information** including limits and specifications

### User Experience
- **Responsive design** optimized for desktop and mobile
- **Dark/light theme** with automatic system detection
- **Professional UI components** with smooth animations
- **Accessibility support** with ARIA labels and keyboard navigation

## 🏗️ Architecture

### Tech Stack
- **Nuxt 3** - Vue.js framework with SSR/SSG support
- **Vue 3** - Composition API with TypeScript
- **Tailwind CSS** - Utility-first styling
- **Headless UI** - Accessible UI components
- **Chart.js** - Interactive data visualization
- **WebSocket API** - Real-time data connection

### Project Structure
```
frontend/
├── assets/css/          # Global styles and themes
├── components/          # Reusable Vue components
│   ├── AppHeader.vue   # Navigation and theme controls
│   ├── Dashboard.vue   # Main trading dashboard
│   ├── StatusIndicator.vue  # Phase and connection status
│   ├── AllocationDisplay.vue # Portfolio allocation charts
│   ├── PnlTracker.vue  # Profit/loss tracking
│   └── PhaseChart.vue  # 4-phase strategy diagram
├── composables/         # Reusable logic
│   ├── useApi.ts       # REST API client
│   ├── useSystemState.ts # Global state management
│   └── useWebSocket.ts # Real-time connection
├── pages/              # Application routes
│   ├── index.vue       # Main dashboard
│   ├── pairs.vue       # Market data browser
│   └── trade/
│       └── new.vue     # Create trading plan
├── types/              # TypeScript definitions
│   └── index.ts        # API and state interfaces
└── nuxt.config.ts      # Nuxt configuration
```

## 📊 4-Phase Strategy Visualization

### Phase Indicators
The dashboard provides real-time visualization of the 4-phase hedging strategy:

**🟢 ADVANCE Phase**
- Both allocations 100% long
- Building positions during uptrends
- Tracking peak prices and units

**🟡 RETRACEMENT Phase** 
- Hedge scales immediately on drops
- Long waits for 2-unit confirmation
- 25% scaling per unit movement

**🔴 DECLINE Phase**
- Long allocation 100% cash (protection)
- Hedge allocation 100% short (profit)
- Positions held to compound gains

**🔵 RECOVERY Phase**
- Systematic re-entry from valleys
- Hedge unwinds shorts immediately
- Long re-enters with confirmation

### Visual Elements
- **Phase badges** with color-coded status
- **Unit tracking** showing distance from peaks/valleys
- **Allocation pie charts** for long/hedge positions
- **P&L graphs** with price movement correlation
- **Connection status** indicators

## 🔌 Backend Integration

### API Connection
The frontend connects to the HyperTrader backend for:

**REST Endpoints:**
- `GET /api/v1/exchange/pairs` - Available trading pairs
- `POST /api/v1/trade/start` - Create new trading plan
- `GET /api/v1/trade/state/:symbol` - Get trading state
- `GET /api/v1/user/favorites` - User favorite pairs
- `POST /api/v1/user/favorites` - Add favorite pair

**WebSocket Connection:**
- `ws://localhost:3000/ws/:symbol` - Real-time trading data
- Automatic reconnection with exponential backoff
- Message types: `price_update`, `state_update`, `trading_error`

### Configuration
Backend connection is configured in `nuxt.config.ts`:

```typescript
export default defineNuxtConfig({
  runtimeConfig: {
    public: {
      apiBaseUrl: 'http://localhost:3000',
      wsBaseUrl: 'ws://localhost:3000'
    }
  }
})
```

## 🎮 Usage Guide

### Starting Your First Trade

1. **Ensure Backend is Running**
   ```bash
   cd ../backend && uv run python -m app.main
   ```

2. **Navigate to Create Trade**
   - Go to "New Trade" in the navigation
   - Select a trading pair (e.g., BTC/USDC)
   - Enter initial margin amount
   - Set leverage (default: 1x)
   - Review strategy settings

3. **Monitor Live Trading**
   - Return to Dashboard to see real-time updates
   - Watch phase transitions as price moves
   - Monitor allocation adjustments
   - Track P&L performance

### Understanding the Dashboard

**Top Status Bar:**
- Current trading phase with color indicator
- WebSocket connection status
- Last price update timestamp
- Emergency stop/start controls

**Portfolio Section:**
- Total portfolio value
- Long/Hedge allocation breakdown
- Current unit position
- Peak/Valley tracking

**Charts Section:**
- Real-time price chart with unit markers
- P&L progression over time
- Allocation percentage changes
- Phase transition timeline

**System Information:**
- Current system state details
- Trading plan metadata
- Performance metrics
- Error logs and alerts

## 🎨 Customization

### Themes
The app includes light and dark themes:
- Automatic system detection
- Manual toggle in header
- Persistent user preference
- Smooth transitions

### Colors
Phase-specific color coding:
```css
:root {
  --phase-advance: #10b981;    /* Green */
  --phase-retracement: #f59e0b; /* Yellow */
  --phase-decline: #ef4444;     /* Red */
  --phase-recovery: #3b82f6;    /* Blue */
}
```

### Responsive Breakpoints
- **Mobile**: < 640px (collapsed layout)
- **Tablet**: 640px - 1024px (compact grid)
- **Desktop**: > 1024px (full layout)

## 🔧 Development

### Environment Setup
```bash
# Install dependencies
bun install

# Development server with hot reload
bun dev

# Type checking
npm run typecheck

# Build for production
npm run build

# Preview production build
npm run preview
```

### Development Tools
- **Vue DevTools** - Component inspection
- **TypeScript** - Full type checking
- **ESLint** - Code linting
- **Prettier** - Code formatting

### Adding New Components

1. **Create component file:**
   ```bash
   touch components/MyComponent.vue
   ```

2. **Use TypeScript composition API:**
   ```vue
   <script setup lang="ts">
   import type { SystemState } from '~/types'
   
   interface Props {
     data: SystemState
   }
   
   const props = defineProps<Props>()
   </script>
   ```

3. **Import and use:**
   ```vue
   <template>
     <MyComponent :data="systemState" />
   </template>
   ```

## 🚀 Deployment

### Static Site Generation (SSG)
```bash
npm run generate
# Deploy dist/ folder to static hosting
```

### Server-Side Rendering (SSR)
```bash
npm run build
npm run preview
# Deploy .output/ folder to Node.js hosting
```

### Single Page Application (SPA)
```bash
# Add to nuxt.config.ts
export default defineNuxtConfig({
  ssr: false
})
npm run generate
```

### Environment Variables
For production deployment:
```env
NUXT_PUBLIC_API_BASE_URL=https://your-backend.com
NUXT_PUBLIC_WS_BASE_URL=wss://your-backend.com
```

## 🧪 Testing

### Component Testing
```bash
# Run component tests
npm run test

# Watch mode
npm run test:watch

# Coverage report
npm run test:coverage
```

### E2E Testing
```bash
# Run end-to-end tests
npm run test:e2e
```

## 📱 Mobile Experience

### PWA Support
The app includes Progressive Web App features:
- **Offline capability** for cached data
- **Add to home screen** on mobile
- **Push notifications** for trade alerts
- **Background sync** when connection restored

### Touch Optimizations
- **Large tap targets** for mobile interaction
- **Swipe gestures** for navigation
- **Haptic feedback** on supported devices
- **Optimized charts** for touch interaction

## 🔍 Troubleshooting

### Common Issues

**WebSocket Connection Failed:**
- Verify backend is running on port 3000
- Check firewall/proxy settings
- Ensure correct WebSocket URL in config

**No Trading Data:**
- Confirm active trading plan exists
- Check API key configuration in backend
- Verify HyperLiquid testnet access

**Charts Not Loading:**
- Check console for JavaScript errors
- Verify chart.js dependencies
- Clear browser cache

**Styling Issues:**
- Run `npm run dev` to rebuild CSS
- Check for conflicting CSS imports
- Verify Tailwind configuration

### Debug Mode
Enable detailed logging:
```bash
DEBUG=true npm run dev
```

### Performance Monitoring
- Use Vue DevTools for component performance
- Monitor WebSocket message frequency
- Check bundle size with `npm run analyze`

## 🤝 Contributing

### Code Style
- Use TypeScript for all new files
- Follow Vue 3 Composition API patterns
- Maintain component props typing
- Add JSDoc comments for complex functions

### Git Workflow
- Create feature branches from `main`
- Use conventional commit messages
- Test all changes before pushing
- Update documentation as needed

---

**🎯 Ready to Trade!** The HyperTrader frontend provides a professional, real-time interface for monitoring and controlling your automated 4-phase hedging strategy. Connect to your backend and start trading with confidence.