<template>
  <div class="dashboard">
    <h1>HyperTrader Dashboard</h1>
    <div class="dashboard-grid">
      <div class="portfolio-overview">
        <h2>Portfolio Overview</h2>
        <div class="overview-stats">
          <div class="stat-card">
            <div class="stat-value">${{ totalPortfolioValue.toLocaleString() }}</div>
            <div class="stat-label">Total Value</div>
          </div>
          <div class="stat-card">
            <div class="stat-value" :class="totalPnl > 0 ? 'positive' : 'negative'">
              {{ totalPnl > 0 ? '+' : '' }}{{ totalPnl.toFixed(2) }}%
            </div>
            <div class="stat-label">Total P&L</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ activePositions }}</div>
            <div class="stat-label">Active Positions</div>
          </div>
        </div>
      </div>
      
      <div class="active-positions">
        <h2>Active Positions</h2>
        <div class="positions-list">
          <div v-for="position in positions" :key="position.symbol" class="position-item">
            <div class="position-symbol">{{ position.symbol }}</div>
            <div class="position-price">${{ position.currentPrice }}</div>
            <div class="position-pnl" :class="position.pnl > 0 ? 'positive' : 'negative'">
              {{ position.pnl > 0 ? '+' : '' }}{{ position.pnl.toFixed(2) }}%
            </div>
            <div class="position-status" :class="position.status">{{ position.status }}</div>
          </div>
        </div>
      </div>
      
      <div class="recent-activity">
        <h2>Recent Activity</h2>
        <div class="activity-list">
          <div v-for="activity in recentActivity" :key="activity.id" class="activity-item">
            <div class="activity-time">{{ activity.time }}</div>
            <div class="activity-description">{{ activity.description }}</div>
            <div class="activity-status" :class="activity.type">{{ activity.type }}</div>
          </div>
        </div>
      </div>
      
      <div class="quick-actions">
        <h2>Quick Actions</h2>
        <div class="action-buttons">
          <NuxtLink to="/plans/create" class="btn btn-primary">Create Trading Plan</NuxtLink>
          <NuxtLink to="/portfolio" class="btn btn-secondary">Manage Portfolio</NuxtLink>
          <NuxtLink to="/plans" class="btn btn-outline">View All Plans</NuxtLink>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Mock dashboard data - will be replaced with real API calls
const totalPortfolioValue = ref(125000)
const totalPnl = ref(3.45)
const activePositions = ref(3)

const positions = ref([
  {
    symbol: 'BTC',
    currentPrice: 47500,
    pnl: 5.56,
    status: 'active'
  },
  {
    symbol: 'ETH',
    currentPrice: 3100,
    pnl: -2.34,
    status: 'hedged'
  },
  {
    symbol: 'SOL',
    currentPrice: 102.5,
    pnl: 8.21,
    status: 'active'
  }
])

const recentActivity = ref([
  {
    id: 1,
    time: '14:32',
    description: 'BTC hedge triggered at $46,475',
    type: 'hedge'
  },
  {
    id: 2,
    time: '13:15',
    description: 'SOL position entered at $95.20',
    type: 'entry'
  },
  {
    id: 3,
    time: '11:45',
    description: 'ETH profit taken at $3,250',
    type: 'profit'
  }
])
</script>

<style scoped>
.dashboard {
  padding: 2rem;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  margin-top: 2rem;
}

.portfolio-overview,
.active-positions,
.recent-activity,
.quick-actions {
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1.5rem;
}

.overview-stats {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.stat-card {
  flex: 1;
  text-align: center;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 4px;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.stat-label {
  font-size: 0.85rem;
  color: #6c757d;
}

.positions-list,
.activity-list {
  margin-top: 1rem;
}

.position-item,
.activity-item {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  gap: 1rem;
  padding: 0.75rem;
  border-bottom: 1px solid #eee;
  align-items: center;
}

.activity-item {
  grid-template-columns: auto 1fr auto;
}

.position-status,
.activity-status {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.position-status.active,
.activity-status.entry {
  background: #d4edda;
  color: #155724;
}

.position-status.hedged,
.activity-status.hedge {
  background: #fff3cd;
  color: #856404;
}

.activity-status.profit {
  background: #d1ecf1;
  color: #0c5460;
}

.positive {
  color: #28a745;
}

.negative {
  color: #dc3545;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1rem;
}

.btn {
  display: inline-block;
  padding: 0.75rem 1rem;
  text-decoration: none;
  border-radius: 4px;
  text-align: center;
  font-weight: 500;
  transition: background-color 0.2s;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover {
  background: #0056b3;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #545b62;
}

.btn-outline {
  background: transparent;
  color: #007bff;
  border: 1px solid #007bff;
}

.btn-outline:hover {
  background: #007bff;
  color: white;
}

@media (max-width: 768px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  
  .overview-stats {
    flex-direction: column;
  }
}
</style>