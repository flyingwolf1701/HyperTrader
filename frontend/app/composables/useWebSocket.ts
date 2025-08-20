// frontend/composables/useWebSocket.ts

import { ref } from 'vue';
import type { SystemState } from '~/types';

// A reactive reference to hold the WebSocket instance
const ws = ref<WebSocket | null>(null);

/**
 * A Nuxt composable to manage the WebSocket connection to the backend.
 */
export const useWebSocket = () => {
  const systemState = useSystemState(); // Access the global state

  /**
   * Connects to the backend WebSocket endpoint for a given symbol.
   * @param symbol The trading pair to connect to (e.g., 'BTC-PERP').
   */
  const connect = (symbol: string) => {
    // Prevent multiple connections
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      console.log('WebSocket connection already open.');
      return;
    }

    // Replace with your actual backend URL
    const wsUrl = `ws://localhost:8000/ws/${symbol}`;
    console.log(`Connecting to WebSocket at ${wsUrl}...`);

    ws.value = new WebSocket(wsUrl);

    ws.value.onopen = () => {
      console.log(`Successfully connected to WebSocket for ${symbol}`);
    };

    ws.value.onmessage = (event) => {
      try {
        // Parse the incoming message as JSON
        const newState: SystemState = JSON.parse(event.data);
        // Update the global state with the new data from the backend
        systemState.value = newState;
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.value.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.value.onclose = () => {
      console.log(`WebSocket connection for ${symbol} closed.`);
      ws.value = null;
    };
  };

  /**
   * Disconnects the WebSocket connection if it's open.
   */
  const disconnect = () => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.close();
    }
  };

  return {
    connect,
    disconnect,
  };
};