<template>
  <div class="plans-list">
    <div class="page-header">
      <h1>Trading Plans</h1>
      <NuxtLink to="/plans/create" class="btn btn-primary">Create New Plan</NuxtLink>
    </div>
    
    <div class="plans-grid">
      <div v-for="plan in plans" :key="plan.id" class="plan-card">
        <div class="plan-header">
          <h3>{{ plan.symbol }}</h3>
          <span class="plan-status" :class="plan.status">{{ plan.status }}</span>
        </div>
        
        <div class="plan-details">
          <div class="detail-item">
            <span class="label">Allocation:</span>
            <span class="value">{{ plan.allocation }}%</span>
          </div>
          <div class="detail-item">
            <span class="label">Entry Price:</span>
            <span class="value">${{ plan.entryPrice }}</span>
          </div>
          <div class="detail-item">
            <span class="label">Current Price:</span>
            <span class="value">${{ plan.currentPrice }}</span>
          </div>
          <div class="detail-item">
            <span class="label">P&L:</span>
            <span class="value" :class="plan.pnl > 0 ? 'positive' : 'negative'">
              {{ plan.pnl > 0 ? '+' : '' }}{{ plan.pnl.toFixed(2) }}%
            </span>
          </div>
        </div>
        
        <div class="plan-actions">
          <NuxtLink :to="`/plans/${plan.id}`" class="btn btn-sm">View Details</NuxtLink>
          <button class="btn btn-sm btn-danger" @click="stopPlan(plan.id)">Stop Plan</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Mock data - will be replaced with API calls
const plans = ref([
  {
    id: 1,
    symbol: 'BTC',
    status: 'active',
    allocation: 25,
    entryPrice: 45000,
    currentPrice: 47500,
    pnl: 5.56
  },
  {
    id: 2,
    symbol: 'ETH',
    status: 'hedged',
    allocation: 20,
    entryPrice: 3200,
    currentPrice: 3100,
    pnl: -3.13
  }
])

const stopPlan = (planId) => {
  // Stop plan logic will go here
  console.log('Stopping plan:', planId)
}
</script>

<style scoped>
.plans-list {
  padding: 2rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.plans-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.plan-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1.5rem;
  background: white;
}

.plan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.plan-status {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
}

.plan-status.active {
  background: #d4edda;
  color: #155724;
}

.plan-status.hedged {
  background: #fff3cd;
  color: #856404;
}

.plan-details {
  margin: 1rem 0;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  margin: 0.5rem 0;
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

.plan-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.btn {
  padding: 0.5rem 1rem;
  text-decoration: none;
  border-radius: 4px;
  border: none;
  cursor: pointer;
}

.btn-sm {
  padding: 0.25rem 0.75rem;
  font-size: 0.85rem;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-danger {
  background: #dc3545;
  color: white;
}
</style>