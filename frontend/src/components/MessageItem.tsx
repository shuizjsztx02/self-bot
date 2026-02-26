import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import type { Message } from '../types'
import { cn } from '../utils'
import { Wrench, User, Bot, Square } from 'lucide-react'

interface MessageItemProps {
  message: Message
}

function formatArguments(args: string): string {
  try {
    const parsed = typeof args === 'string' ? JSON.parse(args) : args
    return JSON.stringify(parsed, null, 2)
  } catch {
    return typeof args === 'string' ? args : JSON.stringify(args, null, 2)
  }
}

export default function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'
  const isTool = message.role === 'tool'
  const isInterrupted = message.interrupted

  return (
    <div
      className={cn(
        'flex gap-3 p-4',
        isUser ? 'bg-primary-50 dark:bg-primary-900/20' : 'bg-white dark:bg-slate-800'
      )}
    >
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser
            ? 'bg-primary-500 text-white'
            : isTool
            ? 'bg-orange-500 text-white'
            : 'bg-slate-200 dark:bg-slate-700'
        )}
      >
        {isUser && <User size={18} />}
        {isAssistant && <Bot size={18} />}
        {isTool && <Wrench size={18} />}
      </div>

      <div className="flex-1 overflow-hidden">
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mb-2 space-y-2">
            {message.tool_calls.map((tc, index) => (
              <div
                key={tc.id || `tool-${index}`}
                className="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm dark:border-orange-800 dark:bg-orange-900/20"
              >
                <div className="flex items-center gap-2 font-medium text-orange-700 dark:text-orange-300">
                  <Wrench size={14} />
                  {tc.function?.name || 'unknown'}
                </div>
                <pre className="mt-1 text-xs text-orange-600 dark:text-orange-400">
                  {formatArguments(tc.function?.arguments || '{}')}
                </pre>
              </div>
            ))}
          </div>
        )}

        {message.content && (
          <div className="prose prose-sm prose-wrap max-w-none overflow-x-auto">
            <ReactMarkdown
              components={{
                code({ inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '')
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                      {...props}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  )
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        
        {isInterrupted && (
          <div className="mt-2 flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400">
            <Square size={12} className="fill-current" />
            <span>输出已被用户中断</span>
          </div>
        )}
      </div>
    </div>
  )
}
