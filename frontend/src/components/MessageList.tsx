import { useEffect, useRef } from 'react'
import type { Message } from '../types'
import MessageItem from './MessageItem'
import { Loader2 } from 'lucide-react'

interface MessageListProps {
  messages: Message[]
  isLoading: boolean
  streamingContent?: string
}

export default function MessageList({
  messages,
  isLoading,
  streamingContent,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 size={32} className="animate-spin text-primary-500" />
      </div>
    )
  }

  if (messages.length === 0 && !streamingContent) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 text-slate-500 dark:text-slate-400">
        <div className="text-6xl">🤖</div>
        <div className="text-xl font-medium">开始新对话</div>
        <div className="text-sm">输入消息开始与 AI 交流</div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto scrollbar-thin">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
      {streamingContent && (
        <MessageItem
          message={{
            id: 'streaming',
            role: 'assistant',
            content: streamingContent,
            created_at: new Date().toISOString(),
          }}
        />
      )}
      
      <div ref={bottomRef} />
    </div>
  )
}
