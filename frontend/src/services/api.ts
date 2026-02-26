import axios from 'axios'
import type { Conversation, Settings } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

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
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
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
    const response = await api.post('/conversations', data)
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
}

export default api
