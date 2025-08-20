export type PhaseType = "advance" | "retracement" | "decline" | "recovery"

export interface SystemState {
  // Basic Trading Information
  symbol: string
  current_phase: PhaseType
  
  // Price and Unit Information
  entry_price: string  // Decimal as string for precision
  unit_value: string
  peak_price: string | null
  valley_price: string | null
  
  // Unit Tracking
  current_unit: number
  peak_unit: number | null
  valley_unit: number | null
  
  // Allocation Amounts (all in dollars)
  long_invested: string
  long_cash: string
  hedge_long: string
  hedge_short: string
  
  // System Information
  initial_margin: string
  leverage: number
  created_at: string
  updated_at: string
  
  // Performance Tracking
  realized_pnl: string
  unrealized_pnl: string
}

export interface TradingPlanCreate {
  symbol: string
  initial_margin: string
  leverage: number
}

export interface TradingPlanUpdate {
  current_phase?: PhaseType
  peak_price?: string
  valley_price?: string
  current_unit?: number
  peak_unit?: number
  valley_unit?: number
  long_invested?: string
  long_cash?: string
  hedge_long?: string
  hedge_short?: string
  realized_pnl?: string
  unrealized_pnl?: string
}

export interface MarketPair {
  symbol: string
  base: string
  quote: string
  min_amount: number | null
  max_amount: number | null
  min_price: number | null
  max_price: number | null
}

export interface UserFavorite {
  id: number
  symbol: string
  base_asset: string
  quote_asset: string
  exchange: string
  sort_order: number
  notes: string | null
  tags: string[]
  current_price: number | null
  created_at: string
}

export interface PriceData {
  symbol: string
  price: number
  timestamp?: string
}

export interface TradingPlanResponse {
  success: boolean
  plan_id: number
  symbol: string
  entry_price: number
  initial_margin: number
  order_id: string
  system_state: SystemState
}

export interface TradingStateResponse {
  plan_id: number
  system_state: SystemState
  current_price: number | null
  created_at: string
  updated_at: string
}

// WebSocket message types
export interface WebSocketMessage {
  type: 'system_state_update' | 'price_update' | 'error' | 'connection_status'
  data: any
  timestamp: string
}

export interface WebSocketSystemStateUpdate extends WebSocketMessage {
  type: 'system_state_update'
  data: {
    symbol: string
    system_state: SystemState
    current_price: number
  }
}

export interface WebSocketPriceUpdate extends WebSocketMessage {
  type: 'price_update'
  data: PriceData
}

// UI Helper types
export interface AllocationData {
  name: string
  value: number
  percentage: number
  color: string
}

export interface PhaseIndicator {
  phase: PhaseType
  color: string
  icon: string
  description: string
}