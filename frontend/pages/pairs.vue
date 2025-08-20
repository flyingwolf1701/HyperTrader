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
            <NuxtLink to="/pairs" class="text-blue-600 font-medium">Pairs</NuxtLink>
            <NuxtLink to="/trade/new" class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">New Trade</NuxtLink>
          </div>
        </div>
      </nav>
    </header>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8">
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">Trading Pairs</h1>
        <p class="text-gray-600">Browse and manage your favorite trading pairs</p>
      </div>
      
      <!-- Search and Filters -->
      <div class="mb-6 flex flex-col sm:flex-row gap-4">
        <div class="flex-1">
          <input 
            v-model="searchQuery"
            type="text"
            placeholder="Search trading pairs..."
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div class="flex gap-2">
          <select 
            v-model="selectedQuote"
            class="px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Quotes</option>
            <option value="USDC">USDC</option>
            <option value="USDT">USDT</option>
          </select>
          <button 
            @click="showFavoritesOnly = !showFavoritesOnly"
            :class="['px-4 py-2 rounded-md border', showFavoritesOnly ? 'bg-red-500 text-white border-red-500' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50']"
          >
            ❤️ Favorites
          </button>
        </div>
      </div>

      <!-- Trading Pairs Grid -->
      <div v-if="!loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        <div 
          v-for="pair in filteredPairs" 
          :key="pair.symbol"
          class="bg-white rounded-lg shadow-md border border-gray-200 p-4 hover:shadow-lg transition-shadow"
        >
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-lg font-semibold text-gray-900">{{ pair.base }}/{{ pair.quote }}</h3>
            <button 
              @click="toggleFavorite(pair)"
              :class="['text-xl', isFavorite(pair.symbol) ? 'text-red-500' : 'text-gray-400']"
            >
              ❤️
            </button>
          </div>
          
          <div class="space-y-2 mb-4">
            <div class="flex justify-between text-sm">
              <span class="text-gray-500">Price:</span>
              <span class="font-medium">${{ pair.currentPrice?.toLocaleString() || 'Loading...' }}</span>
            </div>
            
            <div class="flex justify-between text-sm">
              <span class="text-gray-500">24h Change:</span>
              <span 
                :class="(pair.change24h || 0) >= 0 ? 'text-green-600' : 'text-red-600'"
                class="font-medium"
              >
                {{ (pair.change24h || 0) >= 0 ? '+' : '' }}{{ (pair.change24h || 0).toFixed(2) }}%
              </span>
            </div>
            
            <div class="flex justify-between text-sm">
              <span class="text-gray-500">Volume:</span>
              <span class="font-medium">{{ formatVolume(pair.volume24h || 0) }}</span>
            </div>
          </div>
          
          <button 
            @click="startTrading(pair)"
            class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors"
          >
            Start Trading
          </button>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="text-center py-12">
        <div class="animate-spin text-4xl mb-4">⭕</div>
        <p class="text-gray-500">Loading trading pairs...</p>
      </div>

      <!-- Empty State -->
      <div v-if="!loading && filteredPairs.length === 0" class="text-center py-12">
        <div class="text-6xl text-gray-300 mb-4">📊</div>
        <h3 class="text-xl font-semibold text-gray-900 mb-2">No trading pairs found</h3>
        <p class="text-gray-500">
          {{ showFavoritesOnly ? 'You haven\'t favorited any pairs yet.' : 'Try adjusting your search or filters.' }}
        </p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
// State
const pairs = ref([
  { symbol: 'BTC/USDC', base: 'BTC', quote: 'USDC', currentPrice: 94250, change24h: 2.5, volume24h: 1250000 },
  { symbol: 'ETH/USDC', base: 'ETH', quote: 'USDC', currentPrice: 3420, change24h: -1.2, volume24h: 850000 },
  { symbol: 'SOL/USDC', base: 'SOL', quote: 'USDC', currentPrice: 245, change24h: 5.8, volume24h: 450000 },
  { symbol: 'ADA/USDC', base: 'ADA', quote: 'USDC', currentPrice: 1.25, change24h: -0.5, volume24h: 320000 },
  { symbol: 'DOT/USDC', base: 'DOT', quote: 'USDC', currentPrice: 8.75, change24h: 3.2, volume24h: 180000 },
  { symbol: 'MATIC/USDC', base: 'MATIC', quote: 'USDC', currentPrice: 0.95, change24h: -2.1, volume24h: 650000 }
])

const favorites = ref(['BTC/USDC', 'ETH/USDC'])
const loading = ref(false)
const searchQuery = ref('')
const selectedQuote = ref('')
const showFavoritesOnly = ref(false)

// Computed
const filteredPairs = computed(() => {
  let filtered = pairs.value

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(pair => 
      pair.symbol.toLowerCase().includes(query) ||
      pair.base.toLowerCase().includes(query) ||
      pair.quote.toLowerCase().includes(query)
    )
  }

  if (selectedQuote.value) {
    filtered = filtered.filter(pair => pair.quote === selectedQuote.value)
  }

  if (showFavoritesOnly.value) {
    filtered = filtered.filter(pair => favorites.value.includes(pair.symbol))
  }

  return filtered
})

// Methods
const isFavorite = (symbol: string) => favorites.value.includes(symbol)

const toggleFavorite = (pair: any) => {
  if (isFavorite(pair.symbol)) {
    favorites.value = favorites.value.filter(s => s !== pair.symbol)
  } else {
    favorites.value.push(pair.symbol)
  }
}

const startTrading = (pair: any) => {
  navigateTo(`/trade/new?symbol=${encodeURIComponent(pair.symbol)}`)
}

const formatVolume = (volume: number) => {
  if (volume >= 1000000) return `${(volume / 1000000).toFixed(1)}M`
  if (volume >= 1000) return `${(volume / 1000).toFixed(1)}K`
  return volume.toString()
}

// Meta tags
useHead({
  title: 'Trading Pairs - HyperTrader',
  meta: [
    { name: 'description', content: 'Browse and manage trading pairs for automated trading strategies.' }
  ]
})
</script>