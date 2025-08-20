<template>
  <header class="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
    <nav class="container mx-auto px-4">
      <div class="flex items-center justify-between h-16">
        <!-- Logo and Brand -->
        <div class="flex items-center space-x-4">
          <NuxtLink to="/" class="flex items-center space-x-2">
            <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-green-500 rounded-lg flex items-center justify-center">
              <UIcon name="i-heroicons-chart-bar" class="text-white text-lg" />
            </div>
            <span class="text-xl font-bold text-gray-900 dark:text-white">HyperTrader</span>
          </NuxtLink>
        </div>

        <!-- Navigation Links -->
        <div class="hidden md:flex items-center space-x-6">
          <NuxtLink 
            to="/" 
            class="nav-link"
            :class="{ 'nav-link-active': $route.path === '/' }"
          >
            <UIcon name="i-heroicons-squares-2x2" class="text-lg mr-1" />
            Dashboard
          </NuxtLink>
          
          <NuxtLink 
            to="/pairs" 
            class="nav-link"
            :class="{ 'nav-link-active': $route.path === '/pairs' }"
          >
            <UIcon name="i-heroicons-chart-pie" class="text-lg mr-1" />
            Markets
          </NuxtLink>
          
          <NuxtLink 
            to="/trade/new" 
            class="nav-link"
            :class="{ 'nav-link-active': $route.path === '/trade/new' }"
          >
            <UIcon name="i-heroicons-plus-circle" class="text-lg mr-1" />
            New Trade
          </NuxtLink>
        </div>

        <!-- Right side actions -->
        <div class="flex items-center space-x-4">
          <!-- Connection Status Indicator -->
          <div class="hidden sm:flex items-center space-x-2">
            <div 
              class="w-2 h-2 rounded-full"
              :class="isConnected ? 'bg-green-500' : 'bg-red-500'"
            ></div>
            <span class="text-sm text-gray-600 dark:text-gray-400">
              {{ isConnected ? 'Connected' : 'Disconnected' }}
            </span>
          </div>

          <!-- Theme Toggle -->
          <UButton
            variant="ghost"
            size="sm"
            @click="toggleColorMode"
            :icon="$colorMode.value === 'dark' ? 'i-heroicons-sun' : 'i-heroicons-moon'"
          />

          <!-- Mobile Menu Button -->
          <UButton
            variant="ghost"
            size="sm"
            class="md:hidden"
            @click="mobileMenuOpen = !mobileMenuOpen"
            :icon="mobileMenuOpen ? 'i-heroicons-x-mark' : 'i-heroicons-bars-3'"
          />
        </div>
      </div>

      <!-- Mobile Navigation -->
      <div v-if="mobileMenuOpen" class="md:hidden border-t border-gray-200 dark:border-gray-700 py-4">
        <div class="space-y-2">
          <NuxtLink 
            to="/" 
            class="mobile-nav-link"
            :class="{ 'mobile-nav-link-active': $route.path === '/' }"
            @click="mobileMenuOpen = false"
          >
            <UIcon name="i-heroicons-squares-2x2" class="text-lg" />
            Dashboard
          </NuxtLink>
          
          <NuxtLink 
            to="/pairs" 
            class="mobile-nav-link"
            :class="{ 'mobile-nav-link-active': $route.path === '/pairs' }"
            @click="mobileMenuOpen = false"
          >
            <UIcon name="i-heroicons-chart-pie" class="text-lg" />
            Markets
          </NuxtLink>
          
          <NuxtLink 
            to="/trade/new" 
            class="mobile-nav-link"
            :class="{ 'mobile-nav-link-active': $route.path === '/trade/new' }"
            @click="mobileMenuOpen = false"
          >
            <UIcon name="i-heroicons-plus-circle" class="text-lg" />
            New Trade
          </NuxtLink>
        </div>

        <!-- Mobile Connection Status -->
        <div class="flex items-center justify-center space-x-2 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div 
            class="w-2 h-2 rounded-full"
            :class="isConnected ? 'bg-green-500' : 'bg-red-500'"
          ></div>
          <span class="text-sm text-gray-600 dark:text-gray-400">
            {{ isConnected ? 'WebSocket Connected' : 'WebSocket Disconnected' }}
          </span>
        </div>
      </div>
    </nav>
  </header>
</template>

<script setup lang="ts">
const { isConnected } = useSystemState()
const colorMode = useColorMode()
const mobileMenuOpen = ref(false)

const toggleColorMode = () => {
  colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
}

// Close mobile menu when route changes
const route = useRoute()
watch(() => route.path, () => {
  mobileMenuOpen.value = false
})
</script>

<style scoped>
.nav-link {
  @apply flex items-center px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white rounded-md transition-colors;
}

.nav-link-active {
  @apply text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20;
}

.mobile-nav-link {
  @apply flex items-center space-x-3 px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors;
}

.mobile-nav-link-active {
  @apply text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20;
}
</style>