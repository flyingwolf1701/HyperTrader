// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  
  // Add missing modules
  modules: [
    '@nuxt/ui', 
    '@nuxt/test-utils', 
    '@nuxt/eslint',
    '@pinia/nuxt'  // Add this for state management
  ],
  
  // Set dev server to port 3001
  devServer: {
    port: 3001
  },
  
  // Configure for backend communication
  nitro: {
    devProxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true
      }
    }
  },
  
  // TypeScript configuration
  typescript: {
    typeCheck: true
  }
})