import { useState, useRef, useEffect } from 'react'
import { Send, Loader2, StopCircle } from 'lucide-react'
import { useChatStore } from '../stores/chatStore'
import { cn } from '../utils'

export default function ChatInput() {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { sendMessage, isStreaming, interruptStream } = useChatStore()

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [input])

  const handleSubmit = async () => {
    if (!input.trim() || isStreaming) return

    const message = input.trim()
    setInput('')
    await sendMessage(message)
  }

  const handleInterrupt = async () => {
    await interruptStream()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="border-t border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <div className="mx-auto flex max-w-4xl items-end gap-2">
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息... (Shift+Enter 换行)"
            disabled={isStreaming}
            rows={1}
            className={cn(
              'w-full resize-none rounded-xl border border-slate-300 bg-slate-50 p-3 pr-12',
              'focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20',
              'disabled:cursor-not-allowed disabled:opacity-50',
              'dark:border-slate-600 dark:bg-slate-700 dark:text-white'
            )}
          />
        </div>
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isStreaming}
          className={cn(
            'flex h-11 w-11 items-center justify-center rounded-xl',
            'bg-primary-500 text-white transition-colors',
            'hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50'
          )}
        >
          {isStreaming ? (
            <Loader2 size={20} className="animate-spin" />
          ) : (
            <Send size={20} />
          )}
        </button>
        {isStreaming && (
          <button
            onClick={handleInterrupt}
            className={cn(
              'flex h-11 w-11 items-center justify-center rounded-xl',
              'bg-white border-2 border-red-500 text-red-500 transition-colors',
              'hover:bg-red-50'
            )}
            title="停止生成"
          >
            <StopCircle size={22} className="fill-red-500" />
          </button>
        )}
      </div>
    </div>
  )
}
