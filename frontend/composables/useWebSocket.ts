// frontend/composables/useWebSocket.ts

export const useWebSocket = () => {
  const { updateSystemState, updateCurrentPrice, setConnectionStatus } = useSystemState()
  
  // Reactive state
  const ws = ref<WebSocket | null>(null)
  const connectionState = ref<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected')
  const error = ref<string | null>(null)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = ref(1000) // Start with 1 second

  // Connection management
  const connect = async (symbol: string) => {
    if (ws.value?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected')
      return
    }

    try {
      connectionState.value = 'connecting'
      error.value = null
      
      // Connect to WebSocket endpoint
      const wsUrl = `ws://localhost:3001/ws/${symbol}`
      ws.value = new WebSocket(wsUrl)

      ws.value.onopen = () => {
        console.log(`WebSocket connected to ${symbol}`)
        connectionState.value = 'connected'
        setConnectionStatus(true)
        reconnectAttempts.value = 0
        reconnectDelay.value = 1000
        error.value = null
      }

      ws.value.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          handleMessage(message)
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }

      ws.value.onclose = (event) => {
        console.log('WebSocket connection closed:', event.code, event.reason)
        connectionState.value = 'disconnected'
        setConnectionStatus(false)
        
        // Attempt to reconnect if not intentionally closed
        if (event.code !== 1000 && reconnectAttempts.value < maxReconnectAttempts) {
          scheduleReconnect(symbol)
        }
      }

      ws.value.onerror = (event) => {
        console.error('WebSocket error:', event)
        connectionState.value = 'error'
        error.value = 'WebSocket connection error'
        setConnectionStatus(false)
      }

    } catch (e) {
      console.error('Failed to create WebSocket connection:', e)
      connectionState.value = 'error'
      error.value = 'Failed to establish connection'
      setConnectionStatus(false)
    }
  }

  const disconnect = () => {
    if (ws.value) {
      ws.value.close()
    }
  }

  return { isConnected, connect, disconnect }
}
