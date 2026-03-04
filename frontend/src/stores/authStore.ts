import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { knowledgeApi } from '../services/knowledgeApi'
import type { User } from '../types/knowledge'

interface AuthState {
  user: User | null
  token: string | null
  refreshToken: string | null
  tokenExpiry: number | null
  isAuthenticated: boolean
  isLoading: boolean
  
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => void
  refreshAccessToken: () => Promise<boolean>
  checkAuth: () => Promise<boolean>
  setUser: (user: User) => void
  setTokens: (accessToken: string, refreshToken?: string, expiresIn?: number) => void
}

const TOKEN_REFRESH_THRESHOLD = 5 * 60 * 1000

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      tokenExpiry: null,
      isAuthenticated: false,
      isLoading: true,

      setTokens: (accessToken: string, refreshToken?: string, expiresIn?: number) => {
        const expiry = expiresIn 
          ? Date.now() + expiresIn * 1000 
          : Date.now() + 30 * 60 * 1000
        
        localStorage.setItem('token', accessToken)
        if (refreshToken) {
          localStorage.setItem('refreshToken', refreshToken)
        }
        
        set({
          token: accessToken,
          refreshToken: refreshToken || get().refreshToken,
          tokenExpiry: expiry,
          isAuthenticated: true,
        })
      },

      login: async (email: string, password: string) => {
        const response = await knowledgeApi.login({ email, password })
        
        get().setTokens(
          response.access_token,
          response.refresh_token,
          response.expires_in
        )
        
        if (response.user) {
          set({ user: response.user })
        }
      },

      register: async (name: string, email: string, password: string) => {
        await knowledgeApi.register({ name, email, password })
      },

      logout: () => {
        localStorage.removeItem('token')
        localStorage.removeItem('refreshToken')
        set({
          user: null,
          token: null,
          refreshToken: null,
          tokenExpiry: null,
          isAuthenticated: false,
        })
      },

      refreshAccessToken: async () => {
        const { refreshToken } = get()
        
        if (!refreshToken) {
          get().logout()
          return false
        }

        try {
          const response = await knowledgeApi.refreshToken(refreshToken)
          
          get().setTokens(
            response.access_token,
            response.refresh_token,
            response.expires_in
          )
          
          if (response.user) {
            set({ user: response.user })
          }
          
          return true
        } catch (error) {
          console.error('Token refresh failed:', error)
          get().logout()
          return false
        }
      },

      checkAuth: async () => {
        const { token, tokenExpiry, refreshToken } = get()
        
        if (!token) {
          set({ isLoading: false, isAuthenticated: false })
          return false
        }

        if (tokenExpiry && Date.now() >= tokenExpiry) {
          if (refreshToken) {
            const success = await get().refreshAccessToken()
            set({ isLoading: false })
            return success
          } else {
            get().logout()
            set({ isLoading: false })
            return false
          }
        }

        if (tokenExpiry && (tokenExpiry - Date.now()) < TOKEN_REFRESH_THRESHOLD) {
          if (refreshToken) {
            await get().refreshAccessToken()
          }
        }

        set({ isLoading: false, isAuthenticated: true })
        return true
      },

      setUser: (user: User) => {
        set({ user })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        refreshToken: state.refreshToken,
        tokenExpiry: state.tokenExpiry,
      }),
    }
  )
)

let refreshInterval: number | null = null

export const startTokenRefreshTimer = () => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
  
  refreshInterval = window.setInterval(async () => {
    const { tokenExpiry, refreshToken, isAuthenticated } = useAuthStore.getState()
    
    if (!isAuthenticated || !refreshToken) {
      return
    }
    
    if (tokenExpiry && (tokenExpiry - Date.now()) < TOKEN_REFRESH_THRESHOLD) {
      console.log('[Auth] Token expiring soon, refreshing...')
      await useAuthStore.getState().refreshAccessToken()
    }
  }, 60 * 1000)
}

export const stopTokenRefreshTimer = () => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
}

export const initAuth = async () => {
  const { checkAuth } = useAuthStore.getState()
  const isAuthenticated = await checkAuth()
  
  if (isAuthenticated) {
    startTokenRefreshTimer()
  }
  
  return isAuthenticated
}
