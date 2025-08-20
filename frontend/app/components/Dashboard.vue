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