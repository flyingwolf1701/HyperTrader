<!-- frontend/components/Dashboard.vue -->
<template>
  <div v-if="state" class="min-h-screen bg-gray-900 text-gray-200 p-4 sm:p-6 lg:p-8">
    <div class="max-w-7xl mx-auto">
      
      <!-- Header -->
      <header class="mb-8">
        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 class="text-3xl font-bold text-white">HyperTrader Dashboard</h1>
            <p class="text-lg text-gray-400">Real-time monitoring for {{ state.symbol }}</p>
          </div>
          <div class="flex items-center gap-4 bg-gray-800 px-4 py-2 rounded-lg shadow-md">
            <span class="font-mono text-2xl text-cyan-400">${{ formatDecimal(state.current_price) }}</span>
            <StatusIndicator :is-connected="isConnected" />
          </div>
        </div>
      </header>

      <!-- Main Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">

        <!-- Phase & PNL Card -->
        <div class="lg:col-span-2 bg-gray-800 p-6 rounded-xl shadow-lg flex flex-col justify-between">
          <div>
            <h2 class="text-sm font-semibold text-gray-400 uppercase mb-2">Current Phase</h2>
            <div class="flex items-center gap-3 mb-6">
              <span :class="phaseColor(state.current_phase)" class="w-4 h-4 rounded-full"></span>
              <p class="text-3xl font-bold capitalize text-white">{{ state.current_phase }}</p>
            </div>
          </div>
          <div>
            <h2 class="text-sm font-semibold text-gray-400 uppercase mb-2">Realized PNL</h2>
            <p :class="pnlColor(state.realized_pnl)" class="text-4xl font-mono font-semibold">
              ${{ formatDecimal(state.realized_pnl) }}
            </p>
          </div>
        </div>

        <!-- Key Metrics Card -->
        <div class="lg:col-span-2 bg-gray-800 p-6 rounded-xl shadow-lg grid grid-cols-2 gap-6">
          <div class="col-span-2">
            <h2 class="text-sm font-semibold text-gray-400 uppercase mb-2">Portfolio Value</h2>
            <p class="text-3xl font-mono font-semibold text-white">${{ formatDecimal(totalPortfolioValue) }}</p>
          </div>
          <div>
            <h2 class="text-sm font-semibold text-gray-400 uppercase">Current Unit</h2>
            <p class="text-2xl font-mono font-semibold text-white">{{ state.current_unit }}</p>
          </div>
          <div>
            <h2 class="text-sm font-semibold text-gray-400 uppercase">Leverage</h2>
            <p class="text-2xl font-mono font-semibold text-white">{{ state.leverage }}x</p>
          </div>
        </div>

        <!-- Long Allocation Card -->
        <div class="md:col-span-1 lg:col-span-2 bg-gray-800 p-6 rounded-xl shadow-lg">
          <h2 class="text-lg font-bold text-white mb-4">Long Allocation</h2>
          <div class="space-y-4">
            <AllocationBar 
              label="Invested" 
              :value="state.long_invested" 
              :total="totalLongAllocation" 
              color-class="bg-green-500"
            />
            <AllocationBar 
              label="Cash" 
              :value="state.long_cash" 
              :total="totalLongAllocation" 
              color-class="bg-gray-500"
            />
          </div>
        </div>

        <!-- Hedge Allocation Card -->
        <div class="md:col-span-1 lg:col-span-2 bg-gray-800 p-6 rounded-xl shadow-lg">
          <h2 class="text-lg font-bold text-white mb-4">Hedge Allocation</h2>
          <div class="space-y-4">
            <AllocationBar 
              label="Long" 
              :value="state.hedge_long" 
              :total="totalHedgeAllocation" 
              color-class="bg-green-500"
            />
            <AllocationBar 
              label="Short" 
              :value="state.hedge_short" 
              :total="totalHedgeAllocation" 
              color-class="bg-red-500"
            />
          </div>
        </div>
        
        <!-- Peak/Valley Tracking Card -->
        <div class="md:col-span-2 lg:col-span-4 bg-gray-800 p-6 rounded-xl shadow-lg grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
                <h3 class="text-sm font-semibold text-gray-400 uppercase mb-2">Peak Tracking</h3>
                <div class="flex justify-between items-baseline">
                    <span class="text-gray-300">Peak Unit:</span>
                    <span class="font-mono text-xl text-white">{{ state.peak_unit ?? 'N/A' }}</span>
                </div>
                <div class="flex justify-between items-baseline">
                    <span class="text-gray-300">Peak Price:</span>
                    <span class="font-mono text-xl text-white">${{ formatDecimal(state.peak_price) ?? 'N/A' }}</span>
                </div>
            </div>
            <div>
                <h3 class="text-sm font-semibold text-gray-400 uppercase mb-2">Valley Tracking</h3>
                <div class="flex justify-between items-baseline">
                    <span class="text-gray-300">Valley Unit:</span>
                    <span class="font-mono text-xl text-white">{{ state.valley_unit ?? 'N/A' }}</span>
                </div>
                 <div class="flex justify-between items-baseline">
                    <span class="text-gray-300">Valley Price:</span>
                    <span class="font-mono text-xl text-white">${{ formatDecimal(state.valley_price) ?? 'N/A' }}</span>
                </div>
            </div>
        </div>

      </div>
    </div>
  </div>
  <div v-else class="flex items-center justify-center h-screen bg-gray-900 text-white">
    <p class="text-2xl">Connecting to HyperTrader...</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useSystemState } from '~/composables/useSystemState';
import { useWebSocket } from '~/composables/useWebSocket';
import StatusIndicator from './StatusIndicator.vue';

// A simple component to be used inside the dashboard for progress bars
const AllocationBar = defineComponent({
  props: {
    label: String,
    value: [Number, String],
    total: [Number, String],
    colorClass: String,
  },
  setup(props) {
    const valueNum = computed(() => parseFloat(props.value?.toString() || '0'));
    const totalNum = computed(() => parseFloat(props.total?.toString() || '1'));
    const percentage = computed(() => {
      if (totalNum.value === 0) return 0;
      return (valueNum.value / totalNum.value) * 100;
    });

    const formatCurrency = (val: number) => {
      return val.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
    };

    return () => h('div', {}, [
      h('div', { class: 'flex justify-between items-center mb-1' }, [
        h('span', { class: 'text-sm font-medium text-gray-300' }, props.label),
        h('span', { class: 'text-sm font-mono text-gray-400' }, formatCurrency(valueNum.value)),
      ]),
      h('div', { class: 'w-full bg-gray-700 rounded-full h-2.5' }, [
        h('div', { class: `${props.colorClass} h-2.5 rounded-full`, style: `width: ${percentage.value}%` }),
      ]),
    ]);
  },
});


const { state } = useSystemState();
const { isConnected } = useWebSocket();

const formatDecimal = (value: string | number | null | undefined, precision = 2) => {
  if (value === null || value === undefined) return '0.00';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return num.toFixed(precision);
};

const totalLongAllocation = computed(() => {
  const invested = parseFloat(state.value?.long_invested?.toString() || '0');
  const cash = parseFloat(state.value?.long_cash?.toString() || '0');
  return invested + cash;
});

const totalHedgeAllocation = computed(() => {
  const long = parseFloat(state.value?.hedge_long?.toString() || '0');
  const short = parseFloat(state.value?.hedge_short?.toString() || '0');
  return long + short;
});

const totalPortfolioValue = computed(() => {
    return totalLongAllocation.value + totalHedgeAllocation.value;
});

const pnlColor = (pnl: string | number | null | undefined) => {
  if (pnl === null || pnl === undefined) return 'text-gray-400';
  const num = typeof pnl === 'string' ? parseFloat(pnl) : pnl;
  if (num > 0) return 'text-green-400';
  if (num < 0) return 'text-red-400';
  return 'text-gray-400';
};

const phaseColor = (phase: string) => {
    switch(phase) {
        case 'advance': return 'bg-green-500';
        case 'recovery': return 'bg-blue-500';
        case 'retracement': return 'bg-yellow-500';
        case 'decline': return 'bg-red-500';
        default: return 'bg-gray-500';
    }
}
</script>
