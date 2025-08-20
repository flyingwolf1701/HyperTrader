<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-6">Portfolio Allocation</h3>
    
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <!-- Long Allocation -->
      <div class="space-y-4">
        <h4 class="text-md font-medium text-gray-700 dark:text-gray-300 flex items-center">
          <UIcon name="i-heroicons-arrow-trending-up" class="mr-2 text-green-500" />
          Long Allocation
        </h4>
        
        <div class="space-y-3">
          <div class="flex justify-between items-center">
            <span class="text-sm text-gray-600 dark:text-gray-400">Invested</span>
            <span class="font-medium text-gray-900 dark:text-white">
              {{ formatCurrency(systemState?.long_invested || '0') }}
            </span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-sm text-gray-600 dark:text-gray-400">Cash</span>
            <span class="font-medium text-gray-900 dark:text-white">
              {{ formatCurrency(systemState?.long_cash || '0') }}
            </span>
          </div>
          <div class="h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
            <div 
              class="h-full bg-green-500 transition-all duration-300"
              :style="{ width: `${longAllocationPercent}%` }"
            ></div>
          </div>
          <div class="text-right">
            <span class="text-sm font-medium text-green-600 dark:text-green-400">
              {{ formatPercent(longAllocationPercent, 1) }} Invested
            </span>
          </div>
        </div>
      </div>

      <!-- Hedge Allocation -->
      <div class="space-y-4">
        <h4 class="text-md font-medium text-gray-700 dark:text-gray-300 flex items-center">
          <UIcon name="i-heroicons-shield-check" class="mr-2 text-blue-500" />
          Hedge Allocation
        </h4>
        
        <div class="space-y-3">
          <div class="flex justify-between items-center">
            <span class="text-sm text-gray-600 dark:text-gray-400">Long Position</span>
            <span class="font-medium text-gray-900 dark:text-white">
              {{ formatCurrency(systemState?.hedge_long || '0') }}
            </span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-sm text-gray-600 dark:text-gray-400">Short Position</span>
            <span class="font-medium text-gray-900 dark:text-white">
              {{ formatCurrency(Math.abs(parseFloat(systemState?.hedge_short || '0'))) }}
            </span>
          </div>
          <div class="h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
            <div 
              class="h-full bg-blue-500 transition-all duration-300"
              :style="{ width: `${hedgeAllocationPercent}%` }"
            ></div>
          </div>
          <div class="text-right">
            <span class="text-sm font-medium text-blue-600 dark:text-blue-400">
              {{ formatPercent(hedgeAllocationPercent, 1) }} Long
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Total Portfolio Summary -->
    <div class="mt-8 pt-6 border-t border-gray-200 dark:border-gray-600">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="text-center">
          <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Total Portfolio</p>
          <p class="text-2xl font-bold text-gray-900 dark:text-white">
            {{ formatCurrency(totalPortfolioValue) }}
          </p>
        </div>
        <div class="text-center">
          <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Initial Margin</p>
          <p class="text-lg font-semibold text-gray-700 dark:text-gray-300">
            {{ formatCurrency(systemState?.initial_margin || '0') }}
          </p>
        </div>
        <div class="text-center">
          <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Leverage</p>
          <p class="text-lg font-semibold text-gray-700 dark:text-gray-300">
            {{ systemState?.leverage || 1 }}x
          </p>
        </div>
      </div>
    </div>

    <!-- Visual Chart Representation -->
    <div class="mt-6">
      <h5 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Allocation Breakdown</h5>
      <div class="flex rounded-lg overflow-hidden h-8">
        <div 
          class="bg-green-500 flex items-center justify-center text-white text-xs font-medium"
          :style="{ width: `${longInvestedPercent}%` }"
          :title="`Long Invested: ${formatPercent(longInvestedPercent, 1)}`"
        >
          <span v-if="longInvestedPercent > 10">L</span>
        </div>
        <div 
          class="bg-green-300 flex items-center justify-center text-gray-700 text-xs font-medium"
          :style="{ width: `${longCashPercent}%` }"
          :title="`Long Cash: ${formatPercent(longCashPercent, 1)}`"
        >
          <span v-if="longCashPercent > 10">C</span>
        </div>
        <div 
          class="bg-blue-500 flex items-center justify-center text-white text-xs font-medium"
          :style="{ width: `${hedgeLongPercent}%` }"
          :title="`Hedge Long: ${formatPercent(hedgeLongPercent, 1)}`"
        >
          <span v-if="hedgeLongPercent > 10">HL</span>
        </div>
        <div 
          class="bg-red-500 flex items-center justify-center text-white text-xs font-medium"
          :style="{ width: `${hedgeShortPercent}%` }"
          :title="`Hedge Short: ${formatPercent(hedgeShortPercent, 1)}`"
        >
          <span v-if="hedgeShortPercent > 10">HS</span>
        </div>
      </div>
      <div class="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-2">
        <span>Long Invested</span>
        <span>Long Cash</span>
        <span>Hedge Long</span>
        <span>Hedge Short</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const { 
  systemState, 
  totalPortfolioValue, 
  longAllocationPercent, 
  hedgeAllocationPercent,
  formatCurrency,
  formatPercent
} = useSystemState()

// Calculate individual allocation percentages for the visual chart
const longInvestedPercent = computed(() => {
  if (!systemState.value || totalPortfolioValue.value === 0) return 0
  return (parseFloat(systemState.value.long_invested) / totalPortfolioValue.value) * 100
})

const longCashPercent = computed(() => {
  if (!systemState.value || totalPortfolioValue.value === 0) return 0
  return (parseFloat(systemState.value.long_cash) / totalPortfolioValue.value) * 100
})

const hedgeLongPercent = computed(() => {
  if (!systemState.value || totalPortfolioValue.value === 0) return 0
  return (parseFloat(systemState.value.hedge_long) / totalPortfolioValue.value) * 100
})

const hedgeShortPercent = computed(() => {
  if (!systemState.value || totalPortfolioValue.value === 0) return 0
  return (Math.abs(parseFloat(systemState.value.hedge_short)) / totalPortfolioValue.value) * 100
})
</script>