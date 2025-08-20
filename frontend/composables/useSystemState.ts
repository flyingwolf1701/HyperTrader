import type { SystemState, PhaseType } from '~/types'

// Global system state management
export const useSystemState = () => {
  // Reactive state
  const systemState = useState<SystemState | null>('systemState', () => null)
  const currentPrice = useState<number | null>('currentPrice', () => null)
  const isConnected = useState<boolean>('isConnected', () => false)
  const lastUpdated = useState<Date | null>('lastUpdated', () => null)

  // Computed values
  const totalPortfolioValue = computed(() => {
    if (!systemState.value) return 0
    return parseFloat(systemState.value.long_invested) + 
           parseFloat(systemState.value.long_cash) + 
           parseFloat(systemState.value.hedge_long) + 
           Math.abs(parseFloat(systemState.value.hedge_short))
  })

  const longAllocationPercent = computed(() => {
    if (!systemState.value) return 0
    const totalLong = parseFloat(systemState.value.long_invested) + parseFloat(systemState.value.long_cash)
    if (totalLong === 0) return 0
    return (parseFloat(systemState.value.long_invested) / totalLong) * 100
  })

  const hedgeAllocationPercent = computed(() => {
    if (!systemState.value) return 0
    const totalHedge = parseFloat(systemState.value.hedge_long) + Math.abs(parseFloat(systemState.value.hedge_short))
    if (totalHedge === 0) return 0
    return (parseFloat(systemState.value.hedge_long) / totalHedge) * 100
  })

  const totalPnL = computed(() => {
    if (!systemState.value) return 0
    return parseFloat(systemState.value.realized_pnl) + parseFloat(systemState.value.unrealized_pnl)
  })

  const pnlPercent = computed(() => {
    if (!systemState.value) return 0
    const initialMargin = parseFloat(systemState.value.initial_margin)
    if (initialMargin === 0) return 0
    return (totalPnL.value / initialMargin) * 100
  })

  const isResetConditionMet = computed(() => {
    if (!systemState.value) return false
    return parseFloat(systemState.value.hedge_short) === 0 && 
           parseFloat(systemState.value.long_cash) === 0
  })

  const isChoppyTradingActive = computed(() => {
    if (!systemState.value) return false
    const totalLong = parseFloat(systemState.value.long_invested) + parseFloat(systemState.value.long_cash)
    const totalHedge = parseFloat(systemState.value.hedge_long) + Math.abs(parseFloat(systemState.value.hedge_short))
    
    // Long allocation partially allocated
    const longPartial = parseFloat(systemState.value.long_invested) > 0 && 
                       parseFloat(systemState.value.long_invested) < totalLong
    
    // Hedge allocation partially allocated (has both long and short)
    const hedgePartial = parseFloat(systemState.value.hedge_long) > 0 && 
                        parseFloat(systemState.value.hedge_short) > 0
    
    return longPartial || hedgePartial
  })

  // Phase information
  const phaseInfo = computed(() => {
    if (!systemState.value) return null
    
    const phaseMap = {
      advance: {
        color: 'green',
        icon: 'i-heroicons-arrow-trending-up',
        description: 'Both allocations building positions during uptrend'
      },
      retracement: {
        color: 'yellow',
        icon: 'i-heroicons-arrow-path',
        description: 'Decline from peak, scaling positions with confirmations'
      },
      decline: {
        color: 'red',
        icon: 'i-heroicons-arrow-trending-down',
        description: 'Long fully cashed, hedge fully short'
      },
      recovery: {
        color: 'blue',
        icon: 'i-heroicons-arrow-up-right',
        description: 'Recovery from valley, systematic re-entry'
      }
    }
    
    return {
      phase: systemState.value.current_phase,
      ...phaseMap[systemState.value.current_phase]
    }
  })

  // Methods
  const updateSystemState = (newState: SystemState) => {
    systemState.value = newState
    lastUpdated.value = new Date()
  }

  const updateCurrentPrice = (price: number) => {
    currentPrice.value = price
    lastUpdated.value = new Date()
  }

  const setConnectionStatus = (connected: boolean) => {
    isConnected.value = connected
  }

  const reset = () => {
    systemState.value = null
    currentPrice.value = null
    isConnected.value = false
    lastUpdated.value = null
  }

  // Format helpers
  const formatCurrency = (value: string | number) => {
    const num = typeof value === 'string' ? parseFloat(value) : value
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(num)
  }

  const formatPercent = (value: number, decimals = 2) => {
    return `${value.toFixed(decimals)}%`
  }

  const formatPrice = (value: string | number, decimals = 4) => {
    const num = typeof value === 'string' ? parseFloat(value) : value
    return num.toFixed(decimals)
  }

  return {
    // State
    systemState: readonly(systemState),
    currentPrice: readonly(currentPrice),
    isConnected: readonly(isConnected),
    lastUpdated: readonly(lastUpdated),
    
    // Computed
    totalPortfolioValue,
    longAllocationPercent,
    hedgeAllocationPercent,
    totalPnL,
    pnlPercent,
    isResetConditionMet,
    isChoppyTradingActive,
    phaseInfo,
    
    // Methods
    updateSystemState,
    updateCurrentPrice,
    setConnectionStatus,
    reset,
    
    // Helpers
    formatCurrency,
    formatPercent,
    formatPrice
  }
}