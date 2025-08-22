<!-- frontend/app.vue -->
<template>
  <div>
    <!-- 
      This NuxtLayout component is required by Nuxt UI. 
      It acts as a placeholder where your actual page content (like index.vue) will be rendered.
    -->
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useWebSocket } from '~/composables/useWebSocket'

// Get the connect and disconnect functions from our composable
const { connect, disconnect } = useWebSocket()

// Call connect() when the application is mounted in the browser
onMounted(() => {
  connect()
})

// Call disconnect() when the application is closed to prevent memory leaks
onUnmounted(() => {
  disconnect()
})
</script>
