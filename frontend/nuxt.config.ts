// frontend/nuxt.config.ts

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  devtools: { enabled: true },
  
  // Switched from TailwindCSS to the more powerful Nuxt UI module
  modules: [
    '@nuxt/ui'
  ],
  
  css: ['~/assets/css/main.css'],

  // This configures the Vite development server to proxy WebSocket requests.
  vite: {
    server: {
      proxy: {
        // Any request to /ws on the Nuxt server will be forwarded
        // to your backend server on port 8000.
        '/ws': {
          target: 'ws://localhost:8000', // Your backend URL
          ws: true,
        },
      },
    },
  },
})
