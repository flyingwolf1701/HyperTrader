<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
    <div class="max-w-md w-full text-center">
      <div class="mb-8">
        <UIcon 
          :name="errorIcon" 
          :class="`text-6xl ${errorIconClass} mx-auto mb-4`"
        />
        <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          {{ errorTitle }}
        </h1>
        <p class="text-gray-600 dark:text-gray-400 mb-6">
          {{ errorMessage }}
        </p>
      </div>

      <div class="space-y-3">
        <UButton 
          color="blue" 
          size="lg" 
          block
          @click="handleError"
        >
          {{ retryText }}
        </UButton>
        
        <UButton 
          color="gray" 
          variant="ghost" 
          size="lg" 
          block
          @click="navigateTo('/')"
        >
          Go to Dashboard
        </UButton>
      </div>

      <div class="mt-8 text-sm text-gray-500 dark:text-gray-400">
        <p>Error Code: {{ error?.statusCode || 'Unknown' }}</p>
        <p v-if="isDev">{{ error?.message }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { NuxtError } from '#app'

interface Props {
  error: NuxtError
}

const props = defineProps<Props>()

const isDev = process.dev

// Error handling logic
const errorIcon = computed(() => {
  const statusCode = props.error?.statusCode
  
  switch (statusCode) {
    case 404:
      return 'i-heroicons-magnifying-glass'
    case 500:
      return 'i-heroicons-exclamation-triangle'
    case 503:
      return 'i-heroicons-server'
    default:
      return 'i-heroicons-x-circle'
  }
})

const errorIconClass = computed(() => {
  const statusCode = props.error?.statusCode
  
  switch (statusCode) {
    case 404:
      return 'text-blue-500'
    case 500:
    case 503:
      return 'text-red-500'
    default:
      return 'text-gray-500'
  }
})

const errorTitle = computed(() => {
  const statusCode = props.error?.statusCode
  
  switch (statusCode) {
    case 404:
      return 'Page Not Found'
    case 500:
      return 'Server Error'
    case 503:
      return 'Service Unavailable'
    default:
      return 'Something Went Wrong'
  }
})

const errorMessage = computed(() => {
  const statusCode = props.error?.statusCode
  
  switch (statusCode) {
    case 404:
      return "The page you're looking for doesn't exist or has been moved."
    case 500:
      return 'An internal server error occurred. Please try again later.'
    case 503:
      return 'The service is temporarily unavailable. Please check your connection.'
    default:
      return 'An unexpected error occurred. Please try refreshing the page.'
  }
})

const retryText = computed(() => {
  const statusCode = props.error?.statusCode
  return statusCode === 404 ? 'Search Again' : 'Try Again'
})

const handleError = () => {
  // Clear the error and reload
  clearError({ redirect: '/' })
}

// Set page title
useHead({
  title: `${errorTitle.value} - HyperTrader`
})
</script>