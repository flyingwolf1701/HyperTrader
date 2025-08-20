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
            <NuxtLink to="/" class="text-gray-600 hover:text-blue-600">Dashboard</NuxtLink>
            <NuxtLink to="/pairs" class="text-gray-600 hover:text-blue-600">Pairs</NuxtLink>
            <span class="text-blue-600 font-medium">New Trade</span>
          </div>
        </div>
      </nav>
    </header>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8">
      <div class="max-w-2xl mx-auto">
        <div class="mb-8">
          <h1 class="text-3xl font-bold text-gray-900 mb-2">Start New Trading Plan</h1>
          <p class="text-gray-600">Configure your 4-phase automated trading strategy</p>
        </div>

        <!-- Trading Plan Form -->
        <div class="bg-white rounded-lg shadow-md border border-gray-200 p-6">
          <form @submit.prevent="createTradingPlan">
            <!-- Trading Pair Selection -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 mb-2">Trading Pair</label>
              <select 
                v-model="form.symbol"
                class="w-full px-4 py-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              >
                <option value="">Select a trading pair...</option>
                <option value="BTC/USDC">BTC/USDC - $94,250</option>
                <option value="ETH/USDC">ETH/USDC - $3,420</option>
                <option value="SOL/USDC">SOL/USDC - $245</option>
                <option value="ADA/USDC">ADA/USDC - $1.25</option>
                <option value="DOT/USDC">DOT/USDC - $8.75</option>
              </select>
              <p class="text-xs text-gray-500 mt-1">Choose from available HyperLiquid trading pairs</p>
            </div>

            <!-- Initial Margin -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 mb-2">Initial Margin</label>
              <div class="relative">
                <span class="absolute left-3 top-3 text-gray-500">$</span>
                <input 
                  v-model.number="form.initialMargin"
                  type="number"
                  step="0.01"
                  min="10"
                  max="100000"
                  placeholder="100.00"
                  class="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>
              <p class="text-xs text-gray-500 mt-1">
                Total margin to allocate (split 50/50 between long and hedge allocations)
              </p>
            </div>

            <!-- Leverage -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 mb-2">Leverage</label>
              <select 
                v-model.number="form.leverage"
                class="w-full px-4 py-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option :value="1">1x - Conservative</option>
                <option :value="2">2x - Moderate</option>
                <option :value="5">5x - Aggressive</option>
                <option :value="10">10x - High Risk</option>
              </select>
              <p class="text-xs text-gray-500 mt-1">Higher leverage = more sensitive unit movements</p>
            </div>

            <!-- Strategy Preview -->
            <div class="mb-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h3 class="text-lg font-semibold text-blue-900 mb-4">Strategy Preview</h3>
              
              <div class="grid grid-cols-2 gap-4 mb-4">
                <div class="bg-white rounded p-3">
                  <p class="text-sm text-gray-600">Position Size</p>
                  <p class="text-lg font-semibold">${{ (form.initialMargin * form.leverage).toLocaleString() }}</p>
                </div>
                <div class="bg-white rounded p-3">
                  <p class="text-sm text-gray-600">Unit Value (5% margin)</p>
                  <p class="text-lg font-semibold">${{ (form.initialMargin * 0.05 / form.leverage).toFixed(2) }}</p>
                </div>
              </div>

              <div class="space-y-2">
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Long Allocation:</span>
                  <span class="font-medium">${{ (form.initialMargin / 2).toFixed(2) }} (50%)</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Hedge Allocation:</span>
                  <span class="font-medium">${{ (form.initialMargin / 2).toFixed(2) }} (50%)</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Initial Phase:</span>
                  <span class="font-medium text-green-600">ADVANCE</span>
                </div>
              </div>
            </div>

            <!-- 4-Phase Strategy Info -->
            <div class="mb-8">
              <h3 class="text-lg font-semibold text-gray-900 mb-4">4-Phase Strategy Overview</h3>
              <div class="grid grid-cols-2 gap-4">
                <div class="p-4 border border-green-200 rounded-lg bg-green-50">
                  <div class="flex items-center mb-2">
                    <span class="text-green-600 mr-2">🟢</span>
                    <h4 class="font-medium text-green-800">ADVANCE</h4>
                  </div>
                  <p class="text-sm text-green-700">Both allocations 100% long, tracking peaks during uptrends</p>
                </div>

                <div class="p-4 border border-yellow-200 rounded-lg bg-yellow-50">
                  <div class="flex items-center mb-2">
                    <span class="text-yellow-600 mr-2">🟡</span>
                    <h4 class="font-medium text-yellow-800">RETRACEMENT</h4>
                  </div>
                  <p class="text-sm text-yellow-700">Hedge scales immediately, Long waits for 2-unit confirmation</p>
                </div>

                <div class="p-4 border border-red-200 rounded-lg bg-red-50">
                  <div class="flex items-center mb-2">
                    <span class="text-red-600 mr-2">🔴</span>
                    <h4 class="font-medium text-red-800">DECLINE</h4>
                  </div>
                  <p class="text-sm text-red-700">Long 100% cash, Hedge 100% short for maximum protection</p>
                </div>

                <div class="p-4 border border-blue-200 rounded-lg bg-blue-50">
                  <div class="flex items-center mb-2">
                    <span class="text-blue-600 mr-2">🔵</span>
                    <h4 class="font-medium text-blue-800">RECOVERY</h4>
                  </div>
                  <p class="text-sm text-blue-700">Systematic re-entry from valleys with confirmation delays</p>
                </div>
              </div>
            </div>

            <!-- Risk Warning -->
            <div class="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div class="flex items-start">
                <span class="text-yellow-600 text-xl mr-3">⚠️</span>
                <div>
                  <h4 class="font-semibold text-yellow-800 mb-1">Testnet Trading</h4>
                  <p class="text-sm text-yellow-700">
                    This will create a trading plan on HyperLiquid testnet with virtual funds. 
                    No real money will be used for this strategy.
                  </p>
                </div>
              </div>
            </div>

            <!-- Submit Buttons -->
            <div class="flex space-x-4">
              <button
                type="submit"
                :disabled="loading || !form.symbol || !form.initialMargin"
                class="flex-1 bg-blue-600 text-white py-3 px-6 rounded-md font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {{ loading ? 'Creating Plan...' : 'Create Trading Plan' }}
              </button>
              
              <NuxtLink 
                to="/"
                class="px-6 py-3 border border-gray-300 rounded-md text-gray-700 font-medium hover:bg-gray-50 transition-colors text-center"
              >
                Cancel
              </NuxtLink>
            </div>
          </form>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
// Form state
const form = ref({
  symbol: '',
  initialMargin: 100,
  leverage: 1
})

const loading = ref(false)

// Get symbol from URL query if provided
const route = useRoute()
if (route.query.symbol) {
  form.value.symbol = route.query.symbol as string
}

// Create trading plan
const createTradingPlan = async () => {
  if (!form.value.symbol || !form.value.initialMargin) {
    return
  }

  loading.value = true
  
  try {
    // API call to create trading plan
    const response = await fetch('http://localhost:3000/api/v1/trade/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        symbol: form.value.symbol,
        initial_margin: form.value.initialMargin,
        leverage: form.value.leverage
      })
    })

    if (response.ok) {
      const data = await response.json()
      
      // Show success message (you could use a toast library)
      alert(`Trading plan created successfully! Plan ID: ${data.plan_id}`)
      
      // Redirect to dashboard
      await navigateTo('/')
    } else {
      const error = await response.json()
      alert(`Error: ${error.detail || 'Failed to create trading plan'}`)
    }
  } catch (error) {
    console.error('Error creating trading plan:', error)
    alert('Failed to connect to backend. Make sure the backend server is running.')
  } finally {
    loading.value = false
  }
}

// Meta tags
useHead({
  title: 'New Trading Plan - HyperTrader',
  meta: [
    { name: 'description', content: 'Create a new automated trading plan with the 4-phase hedging strategy.' }
  ]
})
</script>