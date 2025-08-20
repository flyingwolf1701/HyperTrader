<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow-sm border-b border-gray-200">
      <nav class="container mx-auto px-4">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center space-x-4">
            <NuxtLink to="/" class="flex items-center space-x-2">
              <div class="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
                📈
              </div>
              <span class="text-xl font-bold text-gray-900">HyperTrader</span>
            </NuxtLink>
          </div>
          <div class="flex items-center space-x-6">
            <NuxtLink to="/" class="text-blue-600 font-medium">Dashboard</NuxtLink>
            <NuxtLink to="/pairs" class="text-gray-600 hover:text-blue-600">Pairs</NuxtLink>
            <NuxtLink to="/trade/new" class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">New Trade</NuxtLink>
          </div>
        </div>
      </nav>
    </header>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8">
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">HyperTrader Dashboard</h1>
        <p class="text-gray-600">Advanced 4-Phase Automated Trading System</p>
      </div>

      <!-- Status Cards -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center">
            <div class="p-2 bg-green-100 rounded-lg">
              <span class="text-green-600">🟢</span>
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">Current Phase</p>
              <p class="text-2xl font-semibold text-gray-900">{{ systemState.currentPhase || 'ADVANCE' }}</p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center">
            <div class="p-2 bg-blue-100 rounded-lg">
              <span class="text-blue-600">💰</span>
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">Portfolio Value</p>
              <p class="text-2xl font-semibold text-gray-900">${{ portfolioValue.toLocaleString() }}</p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center">
            <div class="p-2 bg-yellow-100 rounded-lg">
              <span class="text-yellow-600">📊</span>
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">Current Unit</p>
              <p class="text-2xl font-semibold text-gray-900">{{ systemState.currentUnit || 0 }}</p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center">
            <div class="p-2 bg-purple-100 rounded-lg">
              <span class="text-purple-600">🔌</span>
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">Connection</p>
              <p class="text-2xl font-semibold" :class="connectionStatus === 'Connected' ? 'text-green-600' : 'text-red-600'">
                {{ connectionStatus }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Trading Information -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Current Position -->
        <div class="bg-white rounded-lg shadow">
          <div class="px-6 py-4 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-900">Portfolio Allocation</h3>
          </div>
          <div class="p-6">
            <div class="space-y-4">
              <div>
                <div class="flex justify-between text-sm text-gray-600 mb-1">
                  <span>Long Allocation</span>
                  <span>{{ longAllocationPercent.toFixed(1) }}%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                  <div class="bg-green-500 h-2 rounded-full" :style="{ width: longAllocationPercent + '%' }"></div>
                </div>
              </div>
              <div>
                <div class="flex justify-between text-sm text-gray-600 mb-1">
                  <span>Hedge Allocation</span>
                  <span>{{ hedgeAllocationPercent.toFixed(1) }}%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                  <div class="bg-blue-500 h-2 rounded-full" :style="{ width: hedgeAllocationPercent + '%' }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- System Status -->
        <div class="bg-white rounded-lg shadow">
          <div class="px-6 py-4 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-900">System Status</h3>
          </div>
          <div class="p-6">
            <div class="space-y-3">
              <div class="flex justify-between">
                <span class="text-gray-600">Backend API:</span>
                <span class="text-green-600">✅ Online</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">WebSocket:</span>
                <span :class="connectionStatus === 'Connected' ? 'text-green-600' : 'text-red-600'">
                  {{ connectionStatus === 'Connected' ? '✅ Connected' : '❌ Disconnected' }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">Exchange:</span>
                <span class="text-yellow-600">🧪 Testnet</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">Last Update:</span>
                <span class="text-gray-900">{{ lastUpdate }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="mt-8">
        <div class="bg-white rounded-lg shadow">
          <div class="px-6 py-4 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-900">Quick Actions</h3>
          </div>
          <div class="p-6">
            <div class="flex space-x-4">
              <button @click="testConnection" class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
                Test Connection
              </button>
              <NuxtLink to="/trade/new" class="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700">
                Start New Trade
              </NuxtLink>
              <button @click="refreshData" class="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700">
                Refresh Data
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
// Simple reactive state
const systemState = ref({
  currentPhase: 'ADVANCE',
  currentUnit: 0,
  longInvested: 5000,
  longCash: 0,
  hedgeLong: 5000,
  hedgeShort: 0
})

const connectionStatus = ref('Connecting...')
const portfolioValue = computed(() => 
  systemState.value.longInvested + systemState.value.longCash + 
  systemState.value.hedgeLong + Math.abs(systemState.value.hedgeShort)
)

const longAllocationPercent = computed(() => {
  const total = systemState.value.longInvested + systemState.value.longCash
  return total > 0 ? (systemState.value.longInvested / total) * 100 : 0
})

const hedgeAllocationPercent = computed(() => {
  const total = systemState.value.hedgeLong + Math.abs(systemState.value.hedgeShort)
  return total > 0 ? (systemState.value.hedgeLong / total) * 100 : 0
})

const lastUpdate = ref('Just now')

// Test backend connection
const testConnection = async () => {
  try {
    connectionStatus.value = 'Testing...'
    const response = await fetch('http://localhost:3000/health')
    if (response.ok) {
      connectionStatus.value = 'Connected'
    } else {
      connectionStatus.value = 'Error'
    }
  } catch (error) {
    connectionStatus.value = 'Offline'
  }
}

const refreshData = () => {
  lastUpdate.value = new Date().toLocaleTimeString()
  testConnection()
}

// Initialize on mount
onMounted(() => {
  testConnection()
  // Update timestamp every 30 seconds
  setInterval(() => {
    lastUpdate.value = new Date().toLocaleTimeString()
  }, 30000)
})

// Meta tags
useHead({
  title: 'HyperTrader - Dashboard',
  meta: [
    { name: 'description', content: 'Advanced 4-phase automated trading system dashboard' }
  ]
})
</script>