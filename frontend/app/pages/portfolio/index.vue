<template>
  <div class="portfolio">
    <div class="page-header">
      <h1>Portfolio Management</h1>
      <NuxtLink to="/portfolio/settings" class="btn btn-primary">Portfolio Settings</NuxtLink>
    </div>

    <div class="portfolio-summary">
      <div class="summary-cards">
        <div class="summary-card">
          <h3>Total Portfolio Value</h3>
          <div class="value-large">${{ totalValue.toLocaleString() }}</div>
          <div class="change" :class="totalChange > 0 ? 'positive' : 'negative'">
            {{ totalChange > 0 ? '+' : '' }}{{ totalChange.toFixed(2) }}%
          </div>
        </div>

        <div class="summary-card">
          <h3>Cash Reserves</h3>
          <div class="value-large">${{ cashReserves.toLocaleString() }}</div>
          <div class="percentage">{{ ((cashReserves / totalValue) * 100).toFixed(1) }}% of portfolio</div>
        </div>

        <div class="summary-card">
          <h3>Spot Savings</h3>
          <div class="value-large">${{ spotSavings.toLocaleString() }}</div>
          <div class="percentage">Long-term accumulation</div>
        </div>

        <div class="summary-card">
          <h3>Active Positions</h3>
          <div class="value-large">{{ activePositions }}</div>
          <div class="percentage">{{ allocatedPercentage.toFixed(1) }}% allocated</div>
        </div>
      </div>
    </div>

    <div class="allocation-management">
      <h2>Allocation Management</h2>
      <div class="allocation-grid">
        <div v-for="allocation in allocations" :key="allocation.symbol" class="allocation-card">
          <div class="allocation-header">
            <h3>{{ allocation.symbol }}</h3>
            <span class="allocation-percentage">{{ allocation.percentage }}%</span>
          </div>
          
          <div class="allocation-details">
            <div class="detail-row">
              <span>Target Allocation:</span>
              <span>${{ allocation.targetValue.toLocaleString() }}</span>
            </div>
            <div class="detail-row">
              <span>Current Value:</span>
              <span>${{ allocation.currentValue.toLocaleString() }}</span>
            </div>
            <div class="detail-row">
              <span>Difference:</span>
              <span :class="allocation.difference > 0 ? 'positive' : 'negative'">
                {{ allocation.difference > 0 ? '+' : '' }}${{ Math.abs(allocation.difference).toLocaleString() }}
              </span>
            </div>
            <div class="detail-row">
              <span>Status:</span>
              <span class="status" :class="allocation.status">{{ allocation.status }}</span>
            </div>
          </div>

          <div class="allocation-actions">
            <button 
              class="btn btn-sm" 
              :data-testid="`rebalance-${allocation.symbol.toLowerCase()}`"
              @click="rebalance(allocation.symbol)"
            >
              Rebalance
            </button>
            <button class="btn btn-sm btn-secondary" @click="editAllocation(allocation.symbol)">Edit</button>
          </div>
        </div>
      </div>
    </div>

    <div class="rebalancing-controls">
      <h2>Portfolio Actions</h2>
      <div class="controls-grid">
        <button class="btn btn-large btn-primary" @click="rebalanceAll">
          Rebalance Entire Portfolio
        </button>
        <button class="btn btn-large btn-secondary" @click="addAllocation">
          Add New Allocation
        </button>
        <button class="btn btn-large btn-warning" @click="emergencyExit">
          Emergency Exit All Positions
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// Mock portfolio data - will be replaced with API calls
const totalValue = ref(125000)
const cashReserves = ref(31250) // 25% cash reserves
const spotSavings = ref(18750) // 15% in spot savings
const activePositions = ref(3)
const totalChange = ref(2.34)
const allocatedPercentage = ref(60)

const allocations = ref([
  {
    symbol: 'BTC',
    percentage: 25,
    targetValue: 31250,
    currentValue: 33500,
    difference: 2250,
    status: 'over-allocated'
  },
  {
    symbol: 'ETH',
    percentage: 20,
    targetValue: 25000,
    currentValue: 23800,
    difference: -1200,
    status: 'under-allocated'
  },
  {
    symbol: 'SOL',
    percentage: 15,
    targetValue: 18750,
    currentValue: 18950,
    difference: 200,
    status: 'balanced'
  }
])

const rebalance = (symbol) => {
  console.log('Rebalancing:', symbol)
}

const editAllocation = (symbol) => {
  console.log('Editing allocation for:', symbol)
}

const rebalanceAll = () => {
  console.log('Rebalancing entire portfolio')
}

const addAllocation = () => {
  console.log('Adding new allocation')
}

const emergencyExit = () => {
  console.log('Emergency exit triggered')
}
</script>

<style scoped>
.portfolio {
  padding: 2rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin-bottom: 3rem;
}

.summary-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1.5rem;
  background: white;
  text-align: center;
}

.value-large {
  font-size: 2rem;
  font-weight: bold;
  margin: 0.5rem 0;
}

.change.positive, .positive {
  color: #28a745;
}

.change.negative, .negative {
  color: #dc3545;
}

.percentage {
  color: #6c757d;
  font-size: 0.9rem;
}

.allocation-management {
  margin: 3rem 0;
}

.allocation-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.allocation-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1.5rem;
  background: white;
}

.allocation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.allocation-percentage {
  font-size: 1.2rem;
  font-weight: bold;
  color: #007bff;
}

.allocation-details {
  margin: 1rem 0;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  margin: 0.5rem 0;
}

.status {
  font-weight: 600;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
}

.status.balanced {
  background: #d4edda;
  color: #155724;
}

.status.over-allocated {
  background: #fff3cd;
  color: #856404;
}

.status.under-allocated {
  background: #f8d7da;
  color: #721c24;
}

.allocation-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.controls-grid {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-decoration: none;
}

.btn-sm {
  padding: 0.25rem 0.75rem;
  font-size: 0.85rem;
}

.btn-large {
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-warning {
  background: #ffc107;
  color: #212529;
}
</style>