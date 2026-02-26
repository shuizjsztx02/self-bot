import { useKnowledgeStore } from '../stores/knowledgeStore'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Database, FileText, Settings, Trash2, MessageSquare } from 'lucide-react'
import KnowledgeBaseForm from '../components/KnowledgeBaseForm'
import { toast } from '../components/Toast'
import { formatDateShort } from '../utils'
import type { KnowledgeBaseCreate } from '../types/knowledge'

export default function KnowledgeBasePage() {
  const navigate = useNavigate()
  const {
    knowledgeBases,
    isLoading,
    error,
    fetchKnowledgeBases,
    createKnowledgeBase,
    deleteKnowledgeBase,
    clearError,
  } = useKnowledgeStore()

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      navigate('/login')
      return
    }
    fetchKnowledgeBases()
  }, [fetchKnowledgeBases, navigate])

  const handleCreate = async (data: KnowledgeBaseCreate) => {
    setIsCreating(true)
    try {
      await createKnowledgeBase(data)
      setShowCreateForm(false)
      toast.success('创建成功', `知识库 "${data.name}" 已创建`)
    } catch (e: any) {
      toast.error('创建失败', e.message || '请稍后重试')
    } finally {
      setIsCreating(false)
    }
  }

  const handleDelete = async (id: string) => {
    const kb = knowledgeBases.find((k) => k.id === id)
    setIsDeleting(true)
    try {
      await deleteKnowledgeBase(id)
      setShowDeleteConfirm(null)
      toast.success('删除成功', `知识库 "${kb?.name}" 已删除`)
    } catch (e: any) {
      toast.error('删除失败', e.message || '请稍后重试')
    } finally {
      setIsDeleting(false)
    }
  }

  if (isLoading && knowledgeBases.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  if (error && knowledgeBases.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-red-500 mb-4">错误: {error}</div>
          <button
            onClick={() => {
              clearError()
              fetchKnowledgeBases()
            }}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            重试
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="border-b bg-white px-6 py-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-2 text-gray-600 hover:text-primary-600 transition-colors"
              title="返回聊天"
            >
              <MessageSquare className="h-5 w-5" />
              <span className="text-sm font-medium">返回聊天</span>
            </button>
            <div className="h-6 w-px bg-gray-200" />
            <div>
              <h1 className="text-2xl font-bold">知识库管理</h1>
              <p className="text-gray-500 text-sm mt-1">
                共 {knowledgeBases.length} 个知识库
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowCreateForm(true)}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            创建知识库
          </button>
        </div>
      </div>

      <div className="flex-1 p-6 overflow-y-auto">
        {knowledgeBases.length === 0 ? (
          <div className="text-center py-16">
            <Database className="h-16 w-16 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500 mb-4">暂无知识库</p>
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              创建第一个知识库
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {knowledgeBases.map((kb) => (
              <div
                key={kb.id}
                className="border rounded-lg hover:shadow-md transition-shadow group bg-white"
              >
                <Link
                  to={`/knowledge/${kb.id}`}
                  className="block p-4"
                >
                  <div className="flex items-start justify-between mb-2">
                    <h2 className="text-lg font-semibold truncate flex-1">{kb.name}</h2>
                    <span className={`text-xs px-2 py-1 rounded ${
                      kb.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {kb.is_active ? '活跃' : '停用'}
                    </span>
                  </div>
                  <p className="text-gray-600 text-sm mb-3 line-clamp-2">
                    {kb.description || '暂无描述'}
                  </p>
                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    <div className="flex items-center gap-1">
                      <FileText className="h-4 w-4" />
                      <span>{kb.document_count} 文档</span>
                    </div>
                    <span>{kb.chunk_count} 分块</span>
                  </div>
                  <div className="flex items-center justify-between mt-3 pt-3 border-t text-xs text-gray-400">
                    <span>{kb.embedding_model}</span>
                    <span>{formatDateShort(kb.created_at)}</span>
                  </div>
                </Link>
                <div className="px-4 pb-4 flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Link
                    to={`/knowledge/${kb.id}`}
                    className="p-2 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600"
                    title="设置"
                  >
                    <Settings className="h-4 w-4" />
                  </Link>
                  <button
                    onClick={(e) => {
                      e.preventDefault()
                      setShowDeleteConfirm(kb.id)
                    }}
                    className="p-2 hover:bg-red-50 rounded text-gray-400 hover:text-red-500"
                    title="删除"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showCreateForm && (
        <KnowledgeBaseForm
          onSubmit={handleCreate}
          onCancel={() => setShowCreateForm(false)}
          isLoading={isCreating}
        />
      )}

      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold mb-2">确认删除</h3>
            <p className="text-gray-600 mb-4">
              确定要删除此知识库吗？所有文档和分块数据将被永久删除，此操作不可撤销。
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteConfirm(null)}
                disabled={isDeleting}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={() => handleDelete(showDeleteConfirm)}
                disabled={isDeleting}
                className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
              >
                {isDeleting ? '删除中...' : '删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
