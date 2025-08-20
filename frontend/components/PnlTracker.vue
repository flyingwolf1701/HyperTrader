<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
    <div class="flex items-center justify-between mb-6">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Profit & Loss</h3>
      <UBadge 
        :color="totalPnL >= 0 ? 'green' : 'red'" 
        variant="solid" 
        size="md"
      >
        {{ totalPnL >= 0 ? '+' : '' }}{{ formatCurrency(totalPnL) }}
      </UBadge>
    </div>

    <!-- Main PnL Display -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      <!-- Total PnL -->
      <div class="text-center">
        <div class="flex items-center justify-center mb-2">
          <UIcon 
            :name="totalPnL >= 0 ? 'i-heroicons-arrow-trending-up' : 'i-heroicons-arrow-trending-down'"
            :class="`text-2xl ${totalPnL >= 0 ? 'text-green-500' : 'text-red-500'}`"
          />
        </div>
        <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Total P&L</p>
        <p class="text-2xl font-bold" :class="totalPnL >= 0 ? 'text-green-600' : 'text-red-600'">
          {{ formatCurrency(totalPnL) }}
        </p>
        <p class="text-sm" :class="pnlPercent >= 0 ? 'text-green-500' : 'text-red-500'">
          {{ pnlPercent >= 0 ? '+' : '' }}{{ formatPercent(pnlPercent, 2) }}
        </p>
      </div>

      <!-- Realized PnL -->
      <div class="text-center">
        <div class="flex items-center justify-center mb-2">
          <UIcon 
            name="i-heroicons-banknotes" 
            class="text-2xl text-blue-500"
          />
        </div>
        <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Realized P&L</p>
        <p class="text-xl font-semibold text-gray-900 dark:text-white">
          {{ formatCurrency(systemState?.realized_pnl || '0') }}
        </p>
        <p class="text-xs text-gray-500 dark:text-gray-400">Locked in</p>
      </div>

      <!-- Unrealized PnL -->
      <div class="text-center">
        <div class="flex items-center justify-center mb-2">
          <UIcon 
            name="i-heroicons-clock" 
            class="text-2xl text-orange-500"
          />
        </div>
        <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Unrealized P&L</p>
        <p class="text-xl font-semibold text-gray-900 dark:text-white">
          {{ formatCurrency(systemState?.unrealized_pnl || '0') }}
        </p>
        <p class="text-xs text-gray-500 dark:text-gray-400">Open positions</p>
      </div>

      <!-- Current Price -->
      <div class="text-center">
        <div class="flex items-center justify-center mb-2">
          <UIcon 
            name="i-heroicons-currency-dollar" 
            class="text-2xl text-purple-500"
          />
        </div>
        <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Current Price</p>
        <p class="text-xl font-semibold text-gray-900 dark:text-white">
          {{ currentPrice ? formatPrice(currentPrice, 2) : 'N/A' }}
        </p>
        <p class="text-xs text-gray-500 dark:text-gray-400">
          Entry: {{ systemState ? formatPrice(systemState.entry_price, 2) : 'N/A' }}
        </p>
      </div>
    </div>

    <!-- Price Movement Indicator -->
    <div class="mt-6 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-medium text-gray-700 dark:text-gray-300">Price Movement</span>
        <span class="text-sm text-gray-500 dark:text-gray-400">
          {{ systemState?.current_unit || 0 }} units
        </span>
      </div>
      
      <div class="relative h-6 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
        <!-- Center line -->
        <div class="absolute left-1/2 top-0 w-0.5 h-full bg-gray-400 dark:bg-gray-500 z-10"></div>
        
        <!-- Unit indicator -->
        <div 
          class="absolute top-0 h-full w-1 transition-all duration-300 z-20"
          :class="unitIndicatorClass"
          :style="unitIndicatorStyle"
        ></div>
        
        <!-- Range markers -->
        <div class="absolute inset-0 flex items-center justify-between px-2 text-xs text-gray-500 dark:text-gray-400">
          <span>-10</span>
          <span>-5</span>
          <span class="font-medium">0</span>
          <span>+5</span>
          <span>+10</span>
        </div>
      </div>
      
      <div class="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
        <span>Decline</span>
        <span>Advance</span>
      </div>
    </div>

    <!-- Performance Metrics -->
    <div class="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
      <div>
        <p class="text-xs text-gray-500 dark:text-gray-400">Peak Unit</p>
        <p class="text-sm font-semibold text-gray-900 dark:text-white">
          {{ systemState?.peak_unit || 'N/A' }}
        </p>
      </div>
      <div>
        <p class="text-xs text-gray-500 dark:text-gray-400">Valley Unit</p>
        <p class="text-sm font-semibold text-gray-900 dark:text-white">
          {{ systemState?.valley_unit || 'N/A' }}
        </p>
      </div>
      <div>
        <p class="text-xs text-gray-500 dark:text-gray-400">Unit Value</p>
        <p class="text-sm font-semibold text-gray-900 dark:text-white">
          {{ systemState ? formatCurrency(systemState.unit_value) : 'N/A' }}
        </p>
      </div>
      <div>
        <p class="text-xs text-gray-500 dark:text-gray-400">ROI</p>
        <p class="text-sm font-semibold" :class="pnlPercent >= 0 ? 'text-green-600' : 'text-red-600'">
          {{ formatPercent(pnlPercent, 2) }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const { 
  systemState, 
  currentPrice, 
  totalPnL, 
  pnlPercent,
  formatCurrency,
  formatPercent,
  formatPrice
} = useSystemState()

// Unit indicator positioning and styling
const unitIndicatorStyle = computed(() => {
  if (!systemState.value) return { left: '50%' }
  
  const currentUnit = systemState.value.current_unit
  const maxRange = 10 // -10 to +10 units range
  const position = ((currentUnit + maxRange) / (maxRange * 2)) * 100
  const clampedPosition = Math.max(0, Math.min(100, position))
  
  return {
    left: `${clampedPosition}%`,
    transform: 'translateX(-50%)'
  }
})

const unitIndicatorClass = computed(() => {
  if (!systemState.value) return 'bg-gray-400'
  
  const currentUnit = systemState.value.current_unit
  if (currentUnit > 0) return 'bg-green-500'
  if (currentUnit < 0) return 'bg-red-500'
  return 'bg-gray-400'
})
</script>