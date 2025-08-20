<template>
  <div class="space-y-6">
    <!-- Header with connection status and controls -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
            HyperTrader Dashboard
          </h1>
          <p class="text-gray-600 dark:text-gray-400 mt-1">
            4-Phase Automated Trading System
          </p>
        </div>
        
        <div class="flex items-center space-x-3">
          <!-- Symbol Display -->
          <div v-if="systemState" class="flex items-center space-x-2">
            <UBadge color="blue" variant="soft" size="lg">
              {{ systemState.symbol }}
            </UBadge>
            <span class="text-sm text-gray-500 dark:text-gray-400">
              {{ currentPrice ? formatPrice(currentPrice, 4) : 'Loading...' }}
            </span>
          </div>
          
          <!-- Connection Controls -->
          <UButton
            v-if="!isConnected && !isConnecting"
            @click="connectToSymbol"
            color="green"
            size="sm"
            icon="i-heroicons-play"
          >
            Connect
          </UButton>
          
          <UButton
            v-if="isConnected"
            @click="disconnect"
            color="red"
            size="sm"
            icon="i-heroicons-stop"
          >
            Disconnect
          </UButton>
          
          <div v-if="isConnecting" class="flex items-center space-x-2">
            <UIcon name="i-heroicons-arrow-path" class="animate-spin" />
            <span class="text-sm text-gray-500">Connecting...</span>
          </div>
        </div>
      </div>
      
      <!-- Error Display -->
      <UAlert
        v-if="hasError && error"
        class="mt-4"
        color="red"
        variant="soft"
        :title="'Connection Error'"
        :description="error"
        icon="i-heroicons-exclamation-triangle"
        :close-button="{ icon: 'i-heroicons-x-mark-20-solid', color: 'gray', variant: 'link' }"
        @close="clearError"
      />
    </div>

    <!-- Main Dashboard Content -->
    <div v-if="systemState" class="space-y-6">
      <!-- Status and Phase Information -->
      <StatusIndicator />
      
      <!-- PnL and Portfolio Overview -->
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <PnlTracker />
        <AllocationDisplay />
      </div>
      
      <!-- Phase Chart -->
      <PhaseChart />
      
      <!-- Additional Information Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <!-- Recent Activity -->
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Recent Activity</h3>
          <div class="space-y-3">
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-600 dark:text-gray-400">Phase Change</span>
              <span class="font-medium text-gray-900 dark:text-white">
                {{ systemState.current_phase }}
              </span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-600 dark:text-gray-400">Last Update</span>
              <span class="font-medium text-gray-900 dark:text-white">
                {{ lastUpdated ? formatRelativeTime(lastUpdated) : 'Never' }}
              </span>
            </div>
          </div>
        </div>
        
        <!-- System Metrics -->
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">System Metrics</h3>
          <div class="space-y-3">
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-600 dark:text-gray-400">Trade Started</span>
              <span class="font-medium text-gray-900 dark:text-white">
                {{ formatDate(systemState.created_at) }}
              </span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-600 dark:text-gray-400">Leverage</span>
              <span class="font-medium text-gray-900 dark:text-white">
                {{ systemState.leverage }}x
              </span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-600 dark:text-gray-400">Entry Price</span>
              <span class="font-medium text-gray-900 dark:text-white">
                {{ formatPrice(systemState.entry_price, 4) }}
              </span>
            </div>
          </div>
        </div>
        
        <!-- Quick Actions -->
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Quick Actions</h3>
          <div class="space-y-2">
            <UButton 
              block 
              color="blue" 
              variant="soft" 
              size="sm"
              @click="refreshData"
            >
              Refresh Data
            </UButton>
            <UButton 
              block 
              color="gray" 
              variant="soft" 
              size="sm"
              @click="navigateTo('/pairs')"
            >
              View Markets
            </UButton>
            <UButton 
              block 
              color="green" 
              variant="soft" 
              size="sm"
              @click="navigateTo('/trade/new')"
            >
              New Trade
            </UButton>
          </div>
        </div>
      </div>
    </div>
    
    <!-- No Data State -->
    <div 
      v-else 
      class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-12 text-center"
    >
      <UIcon name="i-heroicons-chart-bar" class="text-4xl text-gray-400 mx-auto mb-4" />
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">No Active Trading Plan</h3>
      <p class="text-gray-600 dark:text-gray-400 mb-6">
        Start by creating a new trading plan or connecting to an existing one.
      </p>
      <div class="flex flex-col sm:flex-row gap-3 justify-center">
        <UButton color="green" @click="navigateTo('/trade/new')">
          Create New Trade
        </UButton>
        <UButton color="gray" variant="ghost" @click="navigateTo('/pairs')">
          Browse Markets
        </UButton>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const { 
  systemState, 
  currentPrice, 
  isConnected, 
  lastUpdated,
  formatCurrency,
  formatPercent,
  formatPrice
} = useSystemState()

const { connect, disconnect, isConnecting, hasError, error } = useWebSocket()

const route = useRoute()
const selectedSymbol = ref<string>('BTC/USDT') // Default symbol

// Connect to WebSocket when component mounts if we have a symbol
onMounted(async () => {
  const symbolFromQuery = route.query.symbol as string
  if (symbolFromQuery) {
    selectedSymbol.value = symbolFromQuery
    await connectToSymbol()
  }
})

const connectToSymbol = async () => {
  if (selectedSymbol.value) {
    await connect(selectedSymbol.value)
  }
}

const clearError = () => {
  // Error clearing would be handled by the WebSocket composable
}

const refreshData = async () => {
  if (isConnected.value && selectedSymbol.value) {
    // Reconnect to refresh the data
    disconnect()
    await nextTick()
    await connectToSymbol()
  }
}

// Formatting helpers
const formatRelativeTime = (date: Date) => {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const seconds = Math.floor(diff / 1000)
  
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString()
}

// Meta for SEO
useHead({
  title: 'HyperTrader Dashboard',
  meta: [
    { name: 'description', content: '4-Phase Automated Trading System Dashboard' }
  ]
})
</script>