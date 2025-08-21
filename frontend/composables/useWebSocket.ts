// frontend/composables/useWebSocket.ts

import { ref } from 'vue'
import { useSystemState } from './useSystemState'
import type { SystemState } from '~/types'

const ws = ref<WebSocket | null>(null)
const isConnected = ref(false)

export function useWebSocket() {
  const { setSystemState } = useSystemState()

  const connect = () => {
    if (process.server) return; // Don't run on server
    if (ws.value) return; // Already connected or connecting

    const wsUrl = `ws://${window.location.host}/ws/123`
    console.log(`[useWebSocket] Attempting to connect to: ${wsUrl}`)
    
    const newWs = new WebSocket(wsUrl)

    newWs.onopen = () => {
      isConnected.value = true
      console.log('[useWebSocket] Connection established.')
    }

    newWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as SystemState
        setSystemState(data)
      } catch (error) {
        console.error('[useWebSocket] Failed to parse message:', error)
      }
    }

    newWs.onerror = (error) => {
      console.error('[useWebSocket] WebSocket Error:', error)
    }

    newWs.onclose = (event) => {
      ws.value = null
      isConnected.value = false
      console.log(`[useWebSocket] Connection closed. Code: ${event.code}`)
    }

    ws.value = newWs
  }

  const disconnect = () => {
    if (ws.value) {
      ws.value.close()
    }
  }

  return { isConnected, connect, disconnect }
}
