<template>
  <div class="bg-gray-800 p-4 rounded-lg shadow-md">
    <h2 class="text-sm font-medium text-gray-400">{{ title }}</h2>
    <div class="mt-2 space-y-2">
      <div class="flex justify-between items-center">
        <span class="text-gray-300">{{ type === 'long' ? 'Long' : 'Long' }}</span>
        <span class="font-mono text-green-400">${{ parseFloat(invested).toFixed(2) }}</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-gray-300">{{ type === 'long' ? 'Cash' : 'Short' }}</span>
        <span class="font-mono" :class="type === 'long' ? 'text-gray-300' : 'text-red-400'">
          ${{ parseFloat(cash).toFixed(2) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps({
  title: String,
  invested: String, // Received as string to maintain precision
  cash: String,     // Received as string to maintain precision
  type: {
    type: String,
    default: 'long', // 'long' or 'hedge'
  },
});
</script>
```vue
<!-- frontend/components/PnlTracker.vue -->
<template>
  <div class="bg-gray-800 p-4 rounded-lg shadow-md">
    <h2 class="text-sm font-medium text-gray-400">Portfolio P&L</h2>
    <div class="mt-2">
      <p class="text-2xl font-semibold" :class="pnl >= 0 ? 'text-green-500' : 'text-red-500'">
        ${{ pnl.toFixed(2) }}
      </p>
      <p class="text-xs text-gray-500">
        vs Initial Margin: ${{ parseFloat(state.initial_margin).toFixed(2) }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { SystemState } from '~/types';

const props = defineProps<{
  state: SystemState;
}>();

// Calculate the current total portfolio value
const pnl = computed(() => {
  // This is a simplified P&L calculation. A real implementation would need to
  // account for the unrealized P&L of the short position more accurately.
  const longValue = parseFloat(props.state.long_invested) + parseFloat(props.state.long_cash);
  const hedgeValue = parseFloat(props.state.hedge_long) + parseFloat(props.state.hedge_short);
  const totalValue = longValue + hedgeValue;
  
  return totalValue - parseFloat(props.state.initial_margin);
});
</script>