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