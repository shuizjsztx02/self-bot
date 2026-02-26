import { useKnowledgeStore } from '../stores/knowledgeStore'
import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { Settings, Trash2, Upload, FileText, RefreshCw, X, ChevronRight, MessageSquare } from 'lucide-react'
import DocumentUploader from '../components/DocumentUploader'
import FolderTree from '../components/FolderTree'
import { toast } from '../components/Toast'
import { formatDateTime, formatFileSize, getDocumentStatusLabel, getDocumentStatusColor } from '../utils'
import knowledgeApi from '../services/knowledgeApi'
import type { Folder, FolderCreate } from '../types/knowledge'

export default function KnowledgeBaseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const {
    currentKB,
    kbStats,
    documents,
    folders,
    currentFolder,
    isLoading,
    error,
    fetchKnowledgeBase,
    fetchDocuments,
    fetchFolders,
    deleteDocument,
    setCurrentFolder,
    createFolder,
    deleteFolder,
    clearError,
  } = useKnowledgeStore()

  const [showUploader, setShowUploader] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [isDeletingDoc, setIsDeletingDoc] = useState(false)
  const [isDeletingFolder, setIsDeletingFolder] = useState(false)
  const [isCreatingFolder, setIsCreatingFolder] = useState(false)

  useEffect(() => {
    if (id) {
      fetchKnowledgeBase(id)
      fetchDocuments(id)
      fetchFolders(id)
    }
  }, [id, fetchKnowledgeBase, fetchDocuments, fetchFolders])

  const handleRefresh = async () => {
    if (!id || refreshing) return
    setRefreshing(true)
    try {
      await Promise.all([
        fetchKnowledgeBase(id),
        fetchDocuments(id, currentFolder?.id),
        fetchFolders(id),
      ])
      toast.success('刷新成功')
    } finally {
      setRefreshing(false)
    }
  }

  const handleUploadComplete = () => {
    setShowUploader(false)
    if (id) {
      fetchDocuments(id, currentFolder?.id)
      fetchKnowledgeBase(id)
    }
    toast.success('上传完成', '文档已成功上传并开始处理')
  }

  const handleUploadError = (err: string) => {
    toast.error('上传失败', err)
  }

  const handleDeleteDocument = async (docId: string) => {
    const doc = documents.find((d) => d.id === docId)
    setIsDeletingDoc(true)
    try {
      await deleteDocument(docId)
      setShowDeleteConfirm(null)
      if (id) {
        fetchKnowledgeBase(id)
      }
      toast.success('删除成功', `文档 "${doc?.filename}" 已删除`)
    } catch (e: any) {
      toast.error('删除失败', e.message || '请稍后重试')
    } finally {
      setIsDeletingDoc(false)
    }
  }

  const handleSelectFolder = (folder: Folder | null) => {
    setCurrentFolder(folder)
    if (id) {
      fetchDocuments(id, folder?.id)
    }
  }

  const handleCreateFolder = async (data: FolderCreate) => {
    if (!id) return
    setIsCreatingFolder(true)
    try {
      await createFolder(id, data)
      fetchFolders(id)
      toast.success('创建成功', `文件夹 "${data.name}" 已创建`)
    } catch (e: any) {
      toast.error('创建失败', e.message || '请稍后重试')
    } finally {
      setIsCreatingFolder(false)
    }
  }

  const handleDeleteFolder = async (folderId: string) => {
    if (!id) return
    const folder = folders.find((f) => f.id === folderId)
    setIsDeletingFolder(true)
    try {
      await deleteFolder(id, folderId)
      if (currentFolder?.id === folderId) {
        setCurrentFolder(null)
        fetchDocuments(id)
      }
      fetchFolders(id)
      toast.success('删除成功', `文件夹 "${folder?.name}" 已删除`)
    } catch (e: any) {
      toast.error('删除失败', e.message || '请稍后重试')
    } finally {
      setIsDeletingFolder(false)
    }
  }

  const handleRenameFolder = async (folderId: string, name: string) => {
    if (!id) return
    try {
      await knowledgeApi.updateFolder(id, folderId, { name })
      fetchFolders(id)
      toast.success('重命名成功')
    } catch (e: any) {
      toast.error('重命名失败', e.message || '请稍后重试')
    }
  }

  const getStatusBadge = (status: string) => {
    return (
      <span className={`text-xs px-2 py-1 rounded ${getDocumentStatusColor(status)}`}>
        {getDocumentStatusLabel(status)}
      </span>
    )
  }

  if (isLoading && !currentKB) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-red-500 mb-4">错误: {error}</div>
          <button
            onClick={() => {
              clearError()
              if (id) {
                fetchKnowledgeBase(id)
                fetchDocuments(id)
                fetchFolders(id)
              }
            }}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            重试
          </button>
        </div>
      </div>
    )
  }

  if (!currentKB) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">知识库不存在</div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="border-b bg-white px-6 py-4">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1 text-gray-600 hover:text-primary-600 transition-colors"
            title="返回聊天"
          >
            <MessageSquare className="h-4 w-4" />
            <span>返回聊天</span>
          </button>
          <ChevronRight className="h-4 w-4" />
          <Link to="/knowledge" className="hover:text-blue-500">知识库</Link>
          <ChevronRight className="h-4 w-4" />
          <span className="text-gray-900">{currentKB.name}</span>
        </div>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{currentKB.name}</h1>
            <p className="text-gray-600 mt-1">{currentKB.description || '暂无描述'}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-2 hover:bg-gray-100 rounded text-gray-500"
              title="刷新"
            >
              <RefreshCw className={`h-5 w-5 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <Link
              to={`/settings`}
              className="p-2 hover:bg-gray-100 rounded text-gray-500"
              title="设置"
            >
              <Settings className="h-5 w-5" />
            </Link>
          </div>
        </div>

        {kbStats && (
          <div className="flex gap-6 mt-4 text-sm">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-gray-400" />
              <span className="text-gray-600">文档: {kbStats.total_documents}</span>
            </div>
            <div className="text-gray-600">
              分块: {kbStats.total_chunks}
            </div>
            <div className="text-gray-600">
              Token: {kbStats.total_tokens.toLocaleString()}
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="w-64 border-r bg-gray-50 p-4 overflow-y-auto">
          <FolderTree
            folders={folders}
            currentFolderId={currentFolder?.id}
            onSelectFolder={handleSelectFolder}
            onCreateFolder={handleCreateFolder}
            onRenameFolder={handleRenameFolder}
            onDeleteFolder={handleDeleteFolder}
            isLoading={isCreatingFolder || isDeletingFolder}
          />
        </div>

        <div className="flex-1 p-6 overflow-y-auto">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold">
                {currentFolder ? currentFolder.name : '全部文档'}
              </h2>
              {currentFolder && (
                <button
                  onClick={() => handleSelectFolder(null)}
                  className="text-sm text-blue-500 hover:underline"
                >
                  查看全部
                </button>
              )}
            </div>
            <button
              onClick={() => setShowUploader(true)}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm flex items-center gap-2"
            >
              <Upload className="h-4 w-4" />
              上传文档
            </button>
          </div>

          {documents.length === 0 ? (
            <div className="text-center py-16">
              <FileText className="h-16 w-16 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500 mb-4">暂无文档</p>
              <button
                onClick={() => setShowUploader(true)}
                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
              >
                上传第一个文档
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="p-4 border rounded-lg hover:shadow-sm transition-shadow group"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <FileText className="h-4 w-4 text-gray-400 flex-shrink-0" />
                        <span className="font-medium truncate">{doc.filename}</span>
                        {getStatusBadge(doc.status)}
                      </div>
                      <div className="flex items-center gap-4 text-sm text-gray-500">
                        <span>{formatFileSize(doc.file_size)}</span>
                        <span>分块: {doc.chunk_count}</span>
                        <span>Token: {doc.token_count.toLocaleString()}</span>
                        <span>{formatDateTime(doc.created_at)}</span>
                      </div>
                      {doc.tags && doc.tags.length > 0 && (
                        <div className="flex gap-1 mt-2">
                          {doc.tags.map((tag, i) => (
                            <span
                              key={i}
                              className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => setShowDeleteConfirm(doc.id)}
                      className="opacity-0 group-hover:opacity-100 p-2 hover:bg-red-50 rounded text-gray-400 hover:text-red-500"
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
      </div>

      {showUploader && id && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="text-lg font-semibold">上传文档</h2>
              <button
                onClick={() => setShowUploader(false)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>
            <div className="p-4">
              <DocumentUploader
                kbId={id}
                folderId={currentFolder?.id}
                onUploadComplete={handleUploadComplete}
                onUploadError={handleUploadError}
              />
            </div>
          </div>
        </div>
      )}

      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold mb-2">确认删除</h3>
            <p className="text-gray-600 mb-4">
              确定要删除此文档吗？此操作不可撤销。
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteConfirm(null)}
                disabled={isDeletingDoc}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={() => handleDeleteDocument(showDeleteConfirm)}
                disabled={isDeletingDoc}
                className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
              >
                {isDeletingDoc ? '删除中...' : '删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
