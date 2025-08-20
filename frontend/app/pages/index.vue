<!-- frontend/pages/index.vue -->
<template>
  <div>
    <div v-if="state">
      <Dashboard :system-state="state" />
    </div>
    <div v-else class="text-center p-8 bg-gray-800 rounded-lg">
      <p class="text-xl text-gray-400">Connecting to trading bot...</p>
      <p class="text-sm mt-2">
        If this persists, ensure the backend is running and a trade has been initiated.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';

// Use the composables to get the state and connect
const state = useSystemState();
const { connect } = useWebSocket();

// When the component mounts, connect to the WebSocket for a specific symbol
// In a real app, this symbol would be dynamic (e.g., from the URL or user selection)
onMounted(() => {
  // Replace 'BTC-PERP' with the symbol of the active trade
  connect('BTC-PERP'); 
});
</script>
```vue
<!-- frontend/components/Dashboard.vue -->
<template>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
    <StatusIndicator :phase="systemState.current_phase" :symbol="systemState.symbol" />
    <PnlTracker :state="systemState" />
    <AllocationDisplay title="Long Allocation" :invested="systemState.long_invested" :cash="systemState.long_cash" />
    <AllocationDisplay title="Hedge Allocation" :invested="systemState.hedge_long" :cash="systemState.hedge_short" type="hedge" />
  </div>
</template>

<script setup lang="ts">
import type { SystemState } from '~/types';

// Define the props this component accepts
defineProps<{
  systemState: SystemState;
}>();
</script>
```vue
<!-- frontend/components/StatusIndicator.vue -->
<template>
  <div class="bg-gray-800 p-4 rounded-lg shadow-md">
    <h2 class="text-sm font-medium text-gray-400">Status</h2>
    <div class="flex items-center mt-2">
      <span :class="phaseColor" class="w-3 h-3 rounded-full mr-3"></span>
      <div>
        <p class="text-lg font-semibold">{{ phase.toUpperCase() }}</p>
        <p class="text-xs text-gray-500">{{ symbol }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  phase: 'advance' | 'retracement' | 'decline' | 'recovery';
  symbol: string;
}>();

// Computes the color of the status dot based on the current phase
const phaseColor = computed(() => {
  switch (props.phase) {
    case 'advance':
      return 'bg-green-500';
    case 'recovery':
      return 'bg-blue-500';
    case 'retracement':
      return 'bg-yellow-500';
    case 'decline':
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
});
</script>
```vue
<!-- frontend/components/AllocationDisplay.vue -->
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