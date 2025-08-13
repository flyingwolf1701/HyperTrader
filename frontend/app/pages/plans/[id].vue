<template>
  <div class="plan-detail">
    <div class="page-header">
      <h1>{{ plan.symbol }} Trading Plan</h1>
      <div class="header-actions">
        <span class="plan-status" :class="plan.status">{{ plan.status }}</span>
        <button class="btn btn-danger" @click="stopPlan">Stop Plan</button>
      </div>
    </div>

    <div class="plan-overview">
      <div class="overview-grid">
        <div class="overview-card">
          <h3>Position Info</h3>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">Entry Price:</span>
              <span class="value">${{ plan.entryPrice }}</span>
            </div>
            <div class="info-item">
              <span class="label">Current Price:</span>
              <span class="value">${{ plan.currentPrice }}</span>
            </div>
            <div class="info-item">
              <span class="label">Position Size:</span>
              <span class="value">{{ plan.positionSize }} {{ plan.symbol }}</span>
            </div>
            <div class="info-item">
              <span class="label">Unrealized P&L:</span>
              <span class="value" :class="plan.pnl > 0 ? 'positive' : 'negative'">
                {{ plan.pnl > 0 ? '+' : '' }}{{ plan.pnl.toFixed(2) }}%
              </span>
            </div>
          </div>
        </div>

        <div class="overview-card">
          <h3>Fibonacci Levels</h3>
          <div class="fibonacci-levels">
            <div v-for="level in fibonacciLevels" :key="level.name" class="level-item">
              <span class="level-name">{{ level.name }}:</span>
              <span class="level-price">${{ level.price }}</span>
              <span class="level-distance" :class="level.triggered ? 'triggered' : ''">
                {{ level.distance }}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="position-chart">
      <h3>Position Monitoring</h3>
      <!-- Real-time chart will go here -->
      <div class="chart-placeholder">
        <p>Real-time price chart and Fibonacci levels visualization</p>
      </div>
    </div>

    <div class="execution-history">
      <h3>Execution History</h3>
      <div class="history-table">
        <div class="table-header">
          <span>Time</span>
          <span>Action</span>
          <span>Price</span>
          <span>Size</span>
          <span>Status</span>
        </div>
        <div v-for="execution in executionHistory" :key="execution.id" class="table-row">
          <span>{{ execution.timestamp }}</span>
          <span>{{ execution.action }}</span>
          <span>${{ execution.price }}</span>
          <span>{{ execution.size }}</span>
          <span class="status" :class="execution.status">{{ execution.status }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const route = useRoute()
const planId = route.params.id

// Mock data - will be replaced with API calls
const plan = ref({
  id: planId,
  symbol: 'BTC',
  status: 'active',
  entryPrice: 45000,
  currentPrice: 47500,
  positionSize: 0.5,
  pnl: 5.56
})

const fibonacciLevels = ref([
  { name: '23% Retracement', price: 46475, distance: 2.16, triggered: false },
  { name: '38% Retracement', price: 45950, distance: 3.26, triggered: false },
  { name: '50% Retracement', price: 45750, distance: 3.68, triggered: false }
])

const executionHistory = ref([
  {
    id: 1,
    timestamp: '2025-01-15 14:30:25',
    action: 'BUY',
    price: 45000,
    size: 0.5,
    status: 'filled'
  },
  {
    id: 2,
    timestamp: '2025-01-15 16:45:12',
    action: 'HEDGE_TRIGGER',
    price: 46475,
    size: 0.25,
    status: 'pending'
  }
])

const stopPlan = () => {
  // Stop plan logic will go here
  console.log('Stopping plan:', planId)
}
</script>

<style scoped>
.plan-detail {
  padding: 2rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.plan-status {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  font-weight: 600;
}

.plan-status.active {
  background: #d4edda;
  color: #155724;
}

.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  margin-bottom: 2rem;
}

.overview-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1.5rem;
  background: white;
}

.info-grid {
  display: grid;
  gap: 0.75rem;
}

.info-item {
  display: flex;
  justify-content: space-between;
}

.label {
  font-weight: 600;
}

.positive {
  color: #28a745;
}

.negative {
  color: #dc3545;
}

.fibonacci-levels {
  display: grid;
  gap: 0.75rem;
}

.level-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 1rem;
  align-items: center;
}

.level-distance.triggered {
  color: #dc3545;
  font-weight: 600;
}

.position-chart {
  margin: 2rem 0;
}

.chart-placeholder {
  height: 300px;
  border: 1px dashed #ddd;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8f9fa;
  border-radius: 8px;
}

.execution-history {
  margin-top: 2rem;
}

.history-table {
  border: 1px solid #ddd;
  border-radius: 8px;
  overflow: hidden;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
  gap: 1rem;
  padding: 1rem;
}

.table-header {
  background: #f8f9fa;
  font-weight: 600;
  border-bottom: 1px solid #ddd;
}

.table-row {
  border-bottom: 1px solid #eee;
}

.table-row:last-child {
  border-bottom: none;
}

.status.filled {
  color: #28a745;
}

.status.pending {
  color: #ffc107;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-danger {
  background: #dc3545;
  color: white;
}
</style>