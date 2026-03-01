import { useEffect, useState } from 'react'
import { useChatStore } from '../stores/chatStore'
import { Plus, MessageSquare, Trash2, Settings, Database, Search, BookOpen, Pencil, Check, X } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

export default function Sidebar() {
  const location = useLocation()
  const {
    conversations,
    currentConversation,
    loadConversations,
    loadConversation,
    deleteConversation,
    updateConversation,
    clearCurrentConversation,
  } = useChatStore()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')

  useEffect(() => {
    loadConversations()
  }, [])

  const handleNewChat = async () => {
    clearCurrentConversation()
  }

  const handleSelectConversation = (id: string) => {
    if (editingId !== id) {
      loadConversation(id)
    }
  }

  const handleDeleteConversation = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    await deleteConversation(id)
  }

  const handleStartEdit = (e: React.MouseEvent, id: string, currentTitle: string) => {
    e.stopPropagation()
    setEditingId(id)
    setEditingTitle(currentTitle || '')
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditingTitle('')
  }

  const handleSaveEdit = async (id: string) => {
    if (editingTitle.trim()) {
      await updateConversation(id, { title: editingTitle.trim() })
    }
    setEditingId(null)
    setEditingTitle('')
  }

  const handleKeyDown = (e: React.KeyboardEvent, id: string) => {
    if (e.key === 'Enter') {
      handleSaveEdit(id)
    } else if (e.key === 'Escape') {
      handleCancelEdit()
    }
  }

  const isActive = (path: string) => location.pathname === path
  const isKnowledgeActive = location.pathname.startsWith('/knowledge')

  return (
    <div className="flex h-full w-64 flex-col border-r border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-700">
        <h1 className="text-lg font-bold text-primary-600 dark:text-primary-400">
          Self-Bot
        </h1>
        <Link
          to="/settings"
          className={`rounded-lg p-2 transition-colors ${
            isActive('/settings')
              ? 'bg-primary-100 text-primary-600 dark:bg-primary-900/30'
              : 'text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700'
          }`}
        >
          <Settings size={18} />
        </Link>
      </div>

      <div className="space-y-1 p-2">
        <Link
          to="/knowledge"
          className={`flex items-center gap-2 rounded-lg p-3 text-sm font-medium transition-colors ${
            isKnowledgeActive
              ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
              : 'text-slate-700 hover:bg-slate-200 dark:text-slate-200 dark:hover:bg-slate-800'
          }`}
        >
          <Database size={18} />
          知识库
        </Link>

        <Link
          to="/search"
          className={`flex items-center gap-2 rounded-lg p-3 text-sm font-medium transition-colors ${
            isActive('/search')
              ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
              : 'text-slate-700 hover:bg-slate-200 dark:text-slate-200 dark:hover:bg-slate-800'
          }`}
        >
          <Search size={18} />
          知识检索
        </Link>
      </div>

      <div className="mx-2 border-t border-slate-200 dark:border-slate-700" />

      <button
        onClick={handleNewChat}
        className="mx-4 my-3 flex items-center gap-2 rounded-lg border border-slate-300 bg-white p-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        <Plus size={18} />
        新对话
      </button>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="px-2 pb-2">
          <div className="mb-2 flex items-center gap-2 px-3 py-2 text-xs font-semibold uppercase text-slate-400 dark:text-slate-500">
            <BookOpen size={14} />
            对话历史
          </div>
          <div className="space-y-1">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => handleSelectConversation(conv.id)}
                className={`group flex cursor-pointer flex-col rounded-lg p-3 transition-colors ${
                  currentConversation?.id === conv.id && isActive('/')
                    ? 'bg-primary-100 dark:bg-primary-900/30'
                    : 'hover:bg-slate-200 dark:hover:bg-slate-800'
                }`}
              >
                <div className="flex min-w-0 items-center justify-between">
                  <div className="flex min-w-0 flex-1 items-center gap-2">
                    <MessageSquare size={16} className="shrink-0 text-slate-400" />
                    {editingId === conv.id ? (
                      <input
                        type="text"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onKeyDown={(e) => handleKeyDown(e, conv.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="flex-1 rounded border border-primary-300 bg-white px-1 py-0.5 text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-primary-600 dark:bg-slate-700 dark:text-slate-200"
                        autoFocus
                      />
                    ) : (
                      <span className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">
                        {conv.title || '新对话'}
                      </span>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                    {editingId === conv.id ? (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleSaveEdit(conv.id)
                          }}
                          className="rounded p-1 hover:bg-green-100 dark:hover:bg-green-900/30"
                        >
                          <Check size={14} className="text-green-600" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleCancelEdit()
                          }}
                          className="rounded p-1 hover:bg-red-100 dark:hover:bg-red-900/30"
                        >
                          <X size={14} className="text-red-500" />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={(e) => handleStartEdit(e, conv.id, conv.title || '')}
                          className="rounded p-1 hover:bg-slate-300 dark:hover:bg-slate-600"
                        >
                          <Pencil size={14} className="text-slate-500" />
                        </button>
                        <button
                          onClick={(e) => handleDeleteConversation(e, conv.id)}
                          className="rounded p-1 hover:bg-slate-300 dark:hover:bg-slate-600"
                        >
                          <Trash2 size={14} className="text-slate-500" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
                {conv.last_message && editingId !== conv.id && (
                  <div className="mt-1 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                    <span className="shrink-0">
                      {conv.last_message.role === 'user' ? '👤' : '🤖'}
                    </span>
                    <span className="truncate">
                      {conv.last_message.content || '...'}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="border-t border-slate-200 p-4 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
        MCP Agent v1.0.0
      </div>
    </div>
  )
}
