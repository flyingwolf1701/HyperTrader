import type { 
  TradingPlanCreate, 
  TradingPlanResponse, 
  TradingStateResponse, 
  MarketPair, 
  UserFavorite, 
  PriceData 
} from '~/types'

export const useApi = () => {
  const baseURL = 'http://localhost:3001/api/v1'
  
  // Generic request wrapper with error handling
  const apiRequest = async <T>(url: string, options: RequestInit = {}): Promise<T> => {
    try {
      const response = await $fetch<T>(`${baseURL}${url}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      })
      return response
    } catch (error: any) {
      console.error(`API Error for ${url}:`, error)
      throw new Error(error.data?.detail || error.message || 'API request failed')
    }
  }

  // Trading Plan APIs
  const startTradingPlan = async (planData: TradingPlanCreate): Promise<TradingPlanResponse> => {
    return apiRequest<TradingPlanResponse>('/trade/start', {
      method: 'POST',
      body: JSON.stringify(planData)
    })
  }

  const getTradingState = async (symbol: string): Promise<TradingStateResponse> => {
    return apiRequest<TradingStateResponse>(`/trade/state/${symbol}`)
  }

  // Exchange APIs
  const getExchangePairs = async (): Promise<MarketPair[]> => {
    return apiRequest<MarketPair[]>('/exchange/pairs')
  }

  const getCurrentPrice = async (symbol: string): Promise<PriceData> => {
    return apiRequest<PriceData>(`/exchange/price/${symbol}`)
  }

  // User Favorites APIs
  const getUserFavorites = async (userId: string = 'default_user'): Promise<UserFavorite[]> => {
    return apiRequest<UserFavorite[]>(`/user/favorites?user_id=${userId}`)
  }

  const addUserFavorite = async (
    symbol: string, 
    userId: string = 'default_user',
    notes?: string,
    tags?: string[]
  ): Promise<{ success: boolean; id: number; symbol: string; message: string }> => {
    const params = new URLSearchParams({ user_id: userId })
    if (notes) params.append('notes', notes)
    if (tags && tags.length > 0) {
      tags.forEach(tag => params.append('tags', tag))
    }
    params.append('symbol', symbol)
    
    return apiRequest<{ success: boolean; id: number; symbol: string; message: string }>(
      `/user/favorites?${params.toString()}`,
      { method: 'POST' }
    )
  }

  const removeUserFavorite = async (
    favoriteId: number, 
    userId: string = 'default_user'
  ): Promise<{ success: boolean; message: string }> => {
    return apiRequest<{ success: boolean; message: string }>(
      `/user/favorites/${favoriteId}?user_id=${userId}`,
      { method: 'DELETE' }
    )
  }

  // Reactive data fetching composables
  const useTradingState = (symbol: string) => {
    const { data, pending, error, refresh } = useLazyAsyncData(
      `trading-state-${symbol}`,
      () => getTradingState(symbol),
      {
        default: () => null,
        server: false
      }
    )

    return {
      tradingState: data,
      loading: pending,
      error,
      refresh
    }
  }

  const useExchangePairs = () => {
    const { data, pending, error, refresh } = useLazyAsyncData(
      'exchange-pairs',
      () => getExchangePairs(),
      {
        default: () => [],
        server: false
      }
    )

    return {
      pairs: data,
      loading: pending,
      error,
      refresh
    }
  }

  const useUserFavorites = (userId: string = 'default_user') => {
    const { data, pending, error, refresh } = useLazyAsyncData(
      `user-favorites-${userId}`,
      () => getUserFavorites(userId),
      {
        default: () => [],
        server: false
      }
    )

    return {
      favorites: data,
      loading: pending,
      error,
      refresh
    }
  }

  return {
    // Direct API methods
    startTradingPlan,
    getTradingState,
    getExchangePairs,
    getCurrentPrice,
    getUserFavorites,
    addUserFavorite,
    removeUserFavorite,
    
    // Reactive composables
    useTradingState,
    useExchangePairs,
    useUserFavorites
  }
}