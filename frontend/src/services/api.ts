import axios from 'axios'
import type { Conversation, Settings } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: any) => void
}> = []

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error)
    } else if (token) {
      promise.resolve(token)
    }
  })
  failedQueue = []
}

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return api(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refreshToken')

      if (!refreshToken) {
        localStorage.removeItem('token')
        localStorage.removeItem('refreshToken')
        isRefreshing = false
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }

      try {
        const response = await axios.post('/api/auth/refresh', {
          refresh_token: refreshToken,
        })

        const { access_token, refresh_token } = response.data

        localStorage.setItem('token', access_token)
        if (refresh_token) {
          localStorage.setItem('refreshToken', refresh_token)
        }

        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        originalRequest.headers.Authorization = `Bearer ${access_token}`

        processQueue(null, access_token)

        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        localStorage.removeItem('token')
        localStorage.removeItem('refreshToken')
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export const chatApi = {
  getSettings: async (): Promise<Settings> => {
    const response = await api.get('/settings')
    return response.data
  },

  createConversation: async (data?: {
    title?: string
    provider?: string
    model?: string
    system_prompt?: string
  }): Promise<Conversation> => {
    const response = await api.post('/conversations', data || {})
    return response.data
  },

  getConversations: async (): Promise<Conversation[]> => {
    const response = await api.get('/conversations')
    return response.data
  },

  getConversation: async (id: string): Promise<Conversation> => {
    const response = await api.get(`/conversations/${id}`)
    return response.data
  },

  deleteConversation: async (id: string): Promise<void> => {
    await api.delete(`/conversations/${id}`)
  },

  updateConversation: async (id: string, data: { title?: string; system_prompt?: string }): Promise<Conversation> => {
    const response = await api.patch(`/conversations/${id}`, data)
    return response.data
  },

  sendMessage: async (data: {
    message: string
    conversation_id?: string
    provider?: string
    model?: string
    system_prompt?: string
  }): Promise<{ conversation_id: string; response: string; tool_calls?: any[] }> => {
    const response = await api.post('/chat', data)
    return response.data
  },

  sendMessageStream: async (
    data: {
      message: string
      conversation_id?: string
      provider?: string
      model?: string
      system_prompt?: string
    },
    onMessage: (event: any) => void,
  ): Promise<{ sessionId: string; abort: () => void }> => {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const abortController = new AbortController()
    let sessionId = ''

    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
      signal: abortController.signal,
    })

    if (response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      window.location.href = '/login'
      return { sessionId: '', abort: () => {} }
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) return { sessionId: '', abort: () => {} }

    ;(async () => {
      while (true) {
        try {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6))
                if (event.session_id && !sessionId) {
                  sessionId = event.session_id
                }
                onMessage(event)
              } catch (e) {
                // Ignore parse errors
              }
            }
          }
        } catch (e: any) {
          if (e.name === 'AbortError') {
            break
          }
          throw e
        }
      }
    })()

    return {
      sessionId,
      abort: () => abortController.abort(),
    }
  },

  interruptStream: async (sessionId: string): Promise<{ status: string }> => {
    const response = await api.post(`/chat/interrupt/${sessionId}`)
    return response.data
  },

  getStreamSessions: async (): Promise<{ total: number; sessions: any[] }> => {
    const response = await api.get('/chat/sessions')
    return response.data
  },

  confirmSkillInstall: async (
    data: {
      skill_slug: string
      install_pip: boolean
      install_npm: boolean
      install_mcp: boolean
      install_bins?: boolean
      env_vars?: Record<string, string>
    },
    onMessage: (event: any) => void,
  ): Promise<void> => {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch('/api/skills/confirm-install', {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    })

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) return

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            onMessage(event)
          } catch {
            // ignore parse errors
          }
        }
      }
    }
  },
}

export default api
