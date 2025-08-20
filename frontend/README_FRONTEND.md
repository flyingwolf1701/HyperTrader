# HyperTrader Frontend

A modern, responsive frontend for the HyperTrader 4-phase automated trading system built with Nuxt 3, Vue 3, and TypeScript.

## Features

### Core Functionality
- **Real-time Dashboard**: Live trading data with WebSocket connections
- **4-Phase Strategy Visualization**: Advanced, Retracement, Decline, Recovery phases
- **Portfolio Management**: Real-time allocation tracking and P&L monitoring
- **Market Data**: Browse available trading pairs and manage favorites
- **Trading Plan Creation**: Intuitive interface for starting new trades

### Technical Features
- **TypeScript**: Full type safety throughout the application
- **Real-time Updates**: WebSocket integration for live data
- **Responsive Design**: Mobile-first approach with desktop optimization
- **Dark Mode**: Built-in theme switching
- **Professional UI**: Modern design with Tailwind CSS and Nuxt UI
- **Error Handling**: Comprehensive error boundaries and user feedback

## Project Structure

```
frontend/
├── components/           # Reusable UI components
│   ├── Dashboard.vue    # Main trading dashboard
│   ├── StatusIndicator.vue    # Phase and connection status
│   ├── AllocationDisplay.vue  # Portfolio allocation charts
│   ├── PnlTracker.vue   # Profit/loss tracking
│   ├── PhaseChart.vue   # Phase progression visualization
│   └── AppHeader.vue    # Navigation header
├── composables/         # Vue composables for state management
│   ├── useSystemState.ts     # Global trading state
│   ├── useWebSocket.ts       # WebSocket connection management
│   └── useApi.ts        # API integration layer
├── pages/              # Application pages
│   ├── index.vue       # Dashboard page
│   ├── pairs.vue       # Trading pairs management
│   └── trade/
│       └── new.vue     # New trading plan creation
├── types/              # TypeScript type definitions
│   └── index.ts        # All type interfaces
├── assets/css/         # Global styles
│   └── main.css        # Custom CSS and Tailwind extensions
└── layouts/            # Layout templates
    └── default.vue     # Default layout
```

## Key Components

### Dashboard (`components/Dashboard.vue`)
- Central hub for trading operations
- Real-time system state display
- WebSocket connection management
- Quick action buttons

### StatusIndicator (`components/StatusIndicator.vue`)
- Current trading phase display
- Connection status monitoring
- Unit position tracking
- Special condition alerts

### AllocationDisplay (`components/AllocationDisplay.vue`)
- Portfolio allocation visualization
- Long/Hedge position breakdown
- Interactive allocation charts
- Total portfolio value

### PnlTracker (`components/PnlTracker.vue`)
- Real-time profit/loss tracking
- Realized vs unrealized P&L
- Price movement indicators
- Performance metrics

### PhaseChart (`components/PhaseChart.vue`)
- 4-phase strategy flow diagram
- Current phase highlighting
- Phase characteristics explanation
- System status indicators

## State Management

### useSystemState
Global state management for trading data:
- System state tracking
- Price updates
- Connection status
- Computed portfolio values
- Formatting utilities

### useWebSocket
WebSocket connection management:
- Automatic reconnection
- Message handling
- Connection state tracking
- Error handling

### useApi
API integration layer:
- RESTful API calls
- Reactive data fetching
- Error handling
- Caching with useLazyAsyncData

## Configuration

The application is configured for:
- **Development Server**: Port 3001
- **Backend API**: http://localhost:3000/api/v1
- **WebSocket**: ws://localhost:3000
- **Proxy Configuration**: API calls proxied to backend

## Development

### Prerequisites
- Node.js 18+ or Bun
- Backend API running on port 3000

### Installation
```bash
# Install dependencies
bun install  # or npm install

# Start development server
bun dev      # or npm run dev
```

### Available Scripts
- `bun dev` - Start development server
- `bun build` - Build for production
- `bun preview` - Preview production build
- `bun test` - Run tests

## Trading System Integration

The frontend integrates with the backend's 4-phase trading system:

1. **ADVANCE Phase**: Both allocations building positions during uptrend
2. **RETRACEMENT Phase**: Decline from peak with confirmation rules
3. **DECLINE Phase**: Long fully cashed, hedge fully short
4. **RECOVERY Phase**: Recovery from valley with systematic re-entry

### Real-time Features
- Live price updates via WebSocket
- Automatic phase transitions
- Portfolio allocation changes
- P&L calculations
- Unit movement tracking

## API Integration

### REST Endpoints
- `GET /exchange/pairs` - Available trading pairs
- `GET /user/favorites` - User favorite pairs
- `POST /trade/start` - Start new trading plan
- `GET /trade/state/:symbol` - Get current state

### WebSocket Connection
- Real-time system state updates
- Price feed integration
- Connection status monitoring
- Automatic reconnection

## UI/UX Features

### Responsive Design
- Mobile-first approach
- Tablet and desktop optimization
- Touch-friendly interactions
- Adaptive navigation

### Accessibility
- ARIA labels and roles
- Keyboard navigation
- Screen reader support
- High contrast mode
- Reduced motion support

### Professional Design
- Modern card-based layout
- Consistent color schemes
- Smooth animations
- Loading states
- Error boundaries

## Deployment

The frontend can be deployed as:
- Static site generation (SSG)
- Server-side rendering (SSR)
- Single-page application (SPA)

Configure deployment target in `nuxt.config.ts`:
```typescript
export default defineNuxtConfig({
  nitro: {
    preset: 'static' // or 'node-server', 'vercel', etc.
  }
})
```

## Browser Support

- Modern browsers with ES6+ support
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Follow the existing code structure
2. Use TypeScript for all new code
3. Ensure responsive design
4. Add appropriate error handling
5. Update this documentation

## License

Part of the HyperTrader project - refer to main project license.