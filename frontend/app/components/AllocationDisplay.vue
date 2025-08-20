<template>
  <div class="allocation-display">
    <div class="allocation-card allocation-long">
      <h3>Long Allocation</h3>
      <div class="allocation-breakdown">
        <div class="allocation-item">
          <span>Invested:</span>
          <span class="amount">${{ formatCurrency(longInvested) }}</span>
        </div>
        <div class="allocation-item">
          <span>Cash:</span>
          <span class="amount">${{ formatCurrency(longCash) }}</span>
        </div>
        <div class="allocation-percentage">
          {{ longAllocationPercent.toFixed(1) }}% Long
        </div>
      </div>
    </div>
    
    <div class="allocation-card allocation-hedge">
      <h3>Hedge Allocation</h3>
      <div class="allocation-breakdown">
        <div class="allocation-item">
          <span>Long:</span>
          <span class="amount">${{ formatCurrency(hedgeLong) }}</span>
        </div>
        <div class="allocation-item">
          <span>Short:</span>
          <span class="amount">${{ formatCurrency(hedgeShort) }}</span>
        </div>
        <div class="allocation-percentage">
          {{ hedgeLongPercent.toFixed(1) }}% Long / {{ hedgeShortPercent.toFixed(1) }}% Short
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  longInvested: number
  longCash: number
  hedgeLong: number
  hedgeShort: number
}

const props = defineProps<Props>()

const longAllocationPercent = computed(() => {
  const total = props.longInvested + props.longCash
  return total === 0 ? 0 : (props.longInvested / total) * 100
})

const hedgeLongPercent = computed(() => {
  const total = props.hedgeLong + props.hedgeShort
  return total === 0 ? 0 : (props.hedgeLong / total) * 100
})

const hedgeShortPercent = computed(() => {
  const total = props.hedgeLong + props.hedgeShort
  return total === 0 ? 0 : (props.hedgeShort / total) * 100
})

const formatCurrency = (amount: number): string => {
  return amount.toLocaleString('en-US', { 
    minimumFractionDigits: 2, 
    maximumFractionDigits: 2 
  })
}
</script>

<style scoped>
.allocation-display {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin: 1rem 0;
}

.allocation-card {
  padding: 1rem;
  border-radius: 8px;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.allocation-breakdown {
  margin-top: 0.5rem;
}

.allocation-item {
  display: flex;
  justify-content: space-between;
  margin: 0.25rem 0;
}

.allocation-percentage {
  font-weight: bold;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-color);
}

.amount {
  font-family: monospace;
  font-weight: bold;
}
</style>
