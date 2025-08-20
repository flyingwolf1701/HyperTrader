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
  
  // CSS configuration
  css: [
    '@/assets/css/main.css'
  ],
  
  // PostCSS configuration
  postcss: {
    plugins: {
      '@tailwindcss/postcss': {},
      autoprefixer: {},
    },
  },
  
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
    typeCheck: false  // Disable for now to avoid vue-tsc issues
  },
  
  // Runtime configuration
  runtimeConfig: {
    // Private keys (only available on server-side)
    
    // Public keys (exposed to client-side)
    public: {
      apiBaseUrl: 'http://localhost:3000/api/v1',
      wsBaseUrl: 'ws://localhost:3000',
      appName: 'HyperTrader',
      version: '1.0.0'
    }
  },
  
  // App configuration
  app: {
    head: {
      charset: 'utf-8',
      viewport: 'width=device-width, initial-scale=1',
      title: 'HyperTrader - Advanced Automated Trading',
      meta: [
        { name: 'description', content: '4-Phase automated trading system with real-time portfolio management' }
      ]
    }
  }
})