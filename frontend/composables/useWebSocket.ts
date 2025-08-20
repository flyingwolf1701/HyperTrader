import type { WebSocketMessage, WebSocketSystemStateUpdate, WebSocketPriceUpdate } from '~/types'

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
      const wsUrl = `ws://localhost:3000/ws/${symbol}`
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
      ws.value.close(1000, 'User requested disconnect')
      ws.value = null
    }
    connectionState.value = 'disconnected'
    setConnectionStatus(false)
    reconnectAttempts.value = 0
  }

  const scheduleReconnect = (symbol: string) => {
    reconnectAttempts.value++
    
    if (reconnectAttempts.value > maxReconnectAttempts) {
      console.log('Max reconnect attempts reached')
      error.value = 'Connection lost and max reconnect attempts exceeded'
      return
    }

    console.log(`Scheduling reconnect attempt ${reconnectAttempts.value} in ${reconnectDelay.value}ms`)
    
    setTimeout(() => {
      connect(symbol)
    }, reconnectDelay.value)
    
    // Exponential backoff with max delay of 30 seconds
    reconnectDelay.value = Math.min(reconnectDelay.value * 2, 30000)
  }

  const handleMessage = (message: WebSocketMessage) => {
    switch (message.type) {
      case 'system_state_update':
        handleSystemStateUpdate(message as WebSocketSystemStateUpdate)
        break
        
      case 'price_update':
        handlePriceUpdate(message as WebSocketPriceUpdate)
        break
        
      case 'error':
        console.error('WebSocket error message:', message.data)
        error.value = message.data.message || 'Unknown error'
        break
        
      case 'connection_status':
        console.log('Connection status:', message.data)
        break
        
      default:
        console.log('Unknown message type:', message.type)
    }
  }

  const handleSystemStateUpdate = (message: WebSocketSystemStateUpdate) => {
    const { system_state, current_price } = message.data
    
    updateSystemState(system_state)
    if (current_price !== null && current_price !== undefined) {
      updateCurrentPrice(current_price)
    }
  }

  const handlePriceUpdate = (message: WebSocketPriceUpdate) => {
    const { price } = message.data
    updateCurrentPrice(price)
  }

  // Cleanup on unmount
  const cleanup = () => {
    disconnect()
  }

  // Auto cleanup when component unmounts
  onUnmounted(() => {
    cleanup()
  })

  return {
    // State
    connectionState: readonly(connectionState),
    error: readonly(error),
    reconnectAttempts: readonly(reconnectAttempts),
    
    // Methods
    connect,
    disconnect,
    cleanup,
    
    // Computed
    isConnected: computed(() => connectionState.value === 'connected'),
    isConnecting: computed(() => connectionState.value === 'connecting'),
    isDisconnected: computed(() => connectionState.value === 'disconnected'),
    hasError: computed(() => connectionState.value === 'error' || error.value !== null)
  }
}