export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  tool_calls?: ToolCall[]
  interrupted?: boolean
  created_at: string
}

export interface ToolCall {
  id: string
  type: string
  function: {
    name: string
    arguments: string
  }
}

export interface LastMessage {
  role: string
  content: string | null
  created_at: string | null
}

export interface Conversation {
  id: string
  title: string
  provider: string
  model?: string
  system_prompt?: string
  messages: Message[]
  created_at: string
  updated_at: string
  last_message?: LastMessage
  message_count?: number
}

export interface Provider {
  name: string
  model: string
  available: boolean
}

export interface Settings {
  default_provider: string
  providers: Provider[]
}
