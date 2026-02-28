import { create } from 'zustand'
import type { Conversation, Message, Settings } from '../types'
import { chatApi } from '../services/api'

interface ChatState {
  conversations: Conversation[]
  currentConversation: Conversation | null
  messages: Message[]
  settings: Settings | null
  isLoading: boolean
  isStreaming: boolean
  streamingContent: string
  currentSessionId: string | null
  abortController: { abort: () => void } | null

  loadSettings: () => Promise<void>
  loadConversations: () => Promise<void>
  loadConversation: (id: string) => Promise<void>
  createConversation: (data?: any) => Promise<Conversation>
  deleteConversation: (id: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  interruptStream: () => Promise<void>
  clearCurrentConversation: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversation: null,
  messages: [],
  settings: null,
  isLoading: false,
  isStreaming: false,
  streamingContent: '',
  currentSessionId: null,
  abortController: null,

  loadSettings: async () => {
    try {
      const settings = await chatApi.getSettings()
      set({ settings })
    } catch (error) {
      console.error('Failed to load settings:', error)
    }
  },

  loadConversations: async () => {
    try {
      const conversations = await chatApi.getConversations()
      set({ conversations })
    } catch (error) {
      console.error('Failed to load conversations:', error)
    }
  },

  loadConversation: async (id: string) => {
    set({ isLoading: true })
    try {
      const conversation = await chatApi.getConversation(id)
      set({
        currentConversation: conversation,
        messages: conversation.messages,
        isLoading: false,
      })
    } catch (error) {
      console.error('Failed to load conversation:', error)
      set({ isLoading: false })
    }
  },

  createConversation: async (data?: any) => {
    const conversation = await chatApi.createConversation(data)
    set((state) => ({
      conversations: [conversation, ...state.conversations],
      currentConversation: conversation,
      messages: [],
    }))
    return conversation
  },

  deleteConversation: async (id: string) => {
    await chatApi.deleteConversation(id)
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      currentConversation:
        state.currentConversation?.id === id ? null : state.currentConversation,
      messages: state.currentConversation?.id === id ? [] : state.messages,
    }))
  },

  sendMessage: async (content: string) => {
    const { settings } = get()
    let { currentConversation } = get()
    
    if (!currentConversation) {
      await get().createConversation()
      currentConversation = get().currentConversation
    }
    
    set({ isStreaming: true, streamingContent: '' })
    
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    set((state) => ({
      messages: [...state.messages, userMessage],
    }))

    let conversationId = currentConversation?.id

    try {
      const { sessionId, abort } = await chatApi.sendMessageStream(
        {
          message: content,
          conversation_id: conversationId,
          provider: settings?.default_provider,
        },
        (event) => {
          if (event.type === 'conversation_id') {
            conversationId = event.id
            if (event.session_id) {
              set({ currentSessionId: event.session_id })
            }
            set((state) => ({
              currentConversation: state.currentConversation || {
                id: event.id,
                title: event.title || '',
                provider: event.provider || '',
                model: event.model || '',
                created_at: event.created_at || '',
                updated_at: event.created_at || '',
                messages: [],
              }
            }))
          } else if (event.type === 'content') {
            set((state) => ({
              streamingContent: state.streamingContent + event.content,
            }))
          } else if (event.type === 'tool_call') {
            const toolMessage: Message = {
              id: `tool_call_${Date.now()}`,
              role: 'assistant',
              content: '',
              tool_calls: [{
                id: `tc_${Date.now()}`,
                type: 'function',
                function: {
                  name: event.name || '',
                  arguments: typeof event.arguments === 'string' 
                    ? event.arguments 
                    : JSON.stringify(event.arguments || {}),
                },
              }],
              created_at: new Date().toISOString(),
            }
            set((state) => ({
              messages: [...state.messages, toolMessage],
            }))
          } else if (event.type === 'tool_result') {
            const resultMessage: Message = {
              id: `tool_result_${Date.now()}`,
              role: 'tool',
              content: event.result || event.content || '',
              created_at: new Date().toISOString(),
            }
            set((state) => ({
              messages: [...state.messages, resultMessage],
            }))
          } else if (event.type === 'interrupted') {
            const streamingContent = get().streamingContent
            if (streamingContent || event.content) {
              const interruptedMessage: Message = {
                id: (Date.now() + 3).toString(),
                role: 'assistant',
                content: event.content || streamingContent,
                interrupted: true,
                created_at: new Date().toISOString(),
              }
              set((state) => ({
                messages: [...state.messages, interruptedMessage],
                streamingContent: '',
                isStreaming: false,
                currentSessionId: null,
                abortController: null,
              }))
            } else {
              set({ 
                isStreaming: false, 
                streamingContent: '',
                currentSessionId: null,
                abortController: null,
              })
            }
          } else if (event.type === 'done') {
            const streamingContent = get().streamingContent
            if (streamingContent) {
              const assistantMessage: Message = {
                id: (Date.now() + 3).toString(),
                role: 'assistant',
                content: streamingContent,
                created_at: new Date().toISOString(),
              }
              set((state) => ({
                messages: [...state.messages, assistantMessage],
                streamingContent: '',
              }))
            }
            set({ 
              isStreaming: false,
              currentSessionId: null,
              abortController: null,
            })
          } else if (event.type === 'error') {
            console.error('Stream error:', event.error)
            const errorMessage: Message = {
              id: `error_${Date.now()}`,
              role: 'assistant',
              content: `错误: ${event.error}`,
              created_at: new Date().toISOString(),
            }
            set((state) => ({
              messages: [...state.messages, errorMessage],
              isStreaming: false,
              currentSessionId: null,
              abortController: null,
            }))
          }
        },
      )
      
      set({ 
        currentSessionId: sessionId,
        abortController: { abort },
      })
    } catch (error) {
      console.error('Failed to send message:', error)
      set({ 
        isStreaming: false,
        currentSessionId: null,
        abortController: null,
      })
    }
  },

  interruptStream: async () => {
    const { currentSessionId, abortController } = get()
    
    if (abortController) {
      abortController.abort()
    }
    
    if (currentSessionId) {
      try {
        await chatApi.interruptStream(currentSessionId)
      } catch (error) {
        console.error('Failed to interrupt stream:', error)
      }
    }
    
    const streamingContent = get().streamingContent
    if (streamingContent) {
      const interruptedMessage: Message = {
        id: `interrupted_${Date.now()}`,
        role: 'assistant',
        content: streamingContent,
        interrupted: true,
        created_at: new Date().toISOString(),
      }
      set((state) => ({
        messages: [...state.messages, interruptedMessage],
        streamingContent: '',
        isStreaming: false,
        currentSessionId: null,
        abortController: null,
      }))
    } else {
      set({ 
        isStreaming: false,
        streamingContent: '',
        currentSessionId: null,
        abortController: null,
      })
    }
  },

  clearCurrentConversation: () => {
    set({
      currentConversation: null,
      messages: [],
    })
  },
}))
