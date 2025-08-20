<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Trading Phase</h3>
      <UBadge 
        :color="phaseInfo?.color || 'gray'" 
        variant="solid" 
        size="md"
        class="uppercase font-bold"
      >
        {{ phaseInfo?.phase || 'Unknown' }}
      </UBadge>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <!-- Phase Status -->
      <div class="flex items-center space-x-3">
        <div class="flex-shrink-0">
          <UIcon 
            :name="phaseInfo?.icon || 'i-heroicons-question-mark-circle'" 
            :class="`text-2xl text-${phaseInfo?.color}-500`"
          />
        </div>
        <div>
          <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Status</p>
          <p class="text-sm text-gray-900 dark:text-white">{{ phaseInfo?.description || 'No data' }}</p>
        </div>
      </div>

      <!-- Connection Status -->
      <div class="flex items-center space-x-3">
        <div class="flex-shrink-0">
          <UIcon 
            :name="connectionIcon" 
            :class="connectionIconClass"
            class="text-2xl"
          />
        </div>
        <div>
          <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Connection</p>
          <p class="text-sm text-gray-900 dark:text-white">{{ connectionStatus }}</p>
        </div>
      </div>

      <!-- Current Unit -->
      <div class="flex items-center space-x-3">
        <div class="flex-shrink-0">
          <UIcon 
            name="i-heroicons-chart-bar" 
            class="text-2xl text-blue-500"
          />
        </div>
        <div>
          <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Current Unit</p>
          <p class="text-lg font-bold text-gray-900 dark:text-white">
            {{ systemState?.current_unit || 0 }}
          </p>
        </div>
      </div>

      <!-- Peak/Valley Units -->
      <div class="flex items-center space-x-3">
        <div class="flex-shrink-0">
          <UIcon 
            name="i-heroicons-arrow-trending-up" 
            class="text-2xl text-purple-500"
          />
        </div>
        <div>
          <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Peak/Valley</p>
          <p class="text-sm text-gray-900 dark:text-white">
            Peak: {{ systemState?.peak_unit || 'N/A' }} / Valley: {{ systemState?.valley_unit || 'N/A' }}
          </p>
        </div>
      </div>
    </div>

    <!-- Special Conditions -->
    <div class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
      <UAlert 
        v-if="isResetConditionMet" 
        title="Reset Conditions Met"
        description="System is ready for portfolio reset and growth scaling"
        icon="i-heroicons-arrow-path"
        color="blue"
      />
      <UAlert 
        v-if="isChoppyTradingActive" 
        title="Choppy Trading Detected"
        description="Faster response times active due to partial allocations"
        icon="i-heroicons-exclamation-triangle"
        color="yellow"
      />
    </div>

    <!-- Last Updated -->
    <div class="mt-4 text-xs text-gray-500 dark:text-gray-400">
      Last updated: {{ lastUpdated ? formatTime(lastUpdated) : 'Never' }}
    </div>
  </div>
</template>

<script setup lang="ts">
const { 
  systemState, 
  isConnected, 
  lastUpdated, 
  phaseInfo, 
  isResetConditionMet, 
  isChoppyTradingActive 
} = useSystemState()

// Connection status computed properties
const connectionStatus = computed(() => {
  return isConnected.value ? 'Connected' : 'Disconnected'
})

const connectionIcon = computed(() => {
  return isConnected.value ? 'i-heroicons-wifi' : 'i-heroicons-wifi-slash'
})

const connectionIconClass = computed(() => {
  return isConnected.value ? 'text-green-500' : 'text-red-500'
})

// Format time helper
const formatTime = (date: Date) => {
  return date.toLocaleTimeString()
}
</script>