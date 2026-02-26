import { useState, useEffect } from 'react'
import knowledgeApi from '../services/knowledgeApi'
import type { Document, DocumentChunk } from '../types/knowledge'
import { DOCUMENT_STATUS_LABELS, FILE_TYPE_LABELS } from '../types/knowledge'
import { getErrorMessage } from '../utils/errorHandler'

interface DocumentDetailProps {
  documentId: string
  open: boolean
  onClose: () => void
  onReprocess?: () => void
}

export function DocumentDetail({ documentId, open, onClose, onReprocess }: DocumentDetailProps) {
  const [document, setDocument] = useState<Document | null>(null)
  const [chunks, setChunks] = useState<DocumentChunk[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'info' | 'chunks'>('info')
  const [selectedChunk, setSelectedChunk] = useState<DocumentChunk | null>(null)

  useEffect(() => {
    if (open && documentId) {
      fetchDocument()
    }
  }, [open, documentId])

  const fetchDocument = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [doc, chunksData] = await Promise.all([
        knowledgeApi.getDocument(documentId),
        knowledgeApi.getDocumentChunks(documentId),
      ])
      setDocument(doc)
      setChunks(chunksData)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleReprocess = async () => {
    if (!document) return
    setIsLoading(true)
    try {
      await knowledgeApi.reprocessDocument(documentId)
      onReprocess?.()
      fetchDocument()
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('zh-CN')
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">
            {document?.filename || '文档详情'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {isLoading && !document && (
            <div className="flex items-center justify-center h-40">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-4">
              {error}
            </div>
          )}

          {document && (
            <>
              {/* Tabs */}
              <div className="flex border-b mb-4">
                <button
                  className={`px-4 py-2 font-medium ${
                    activeTab === 'info'
                      ? 'text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                  onClick={() => setActiveTab('info')}
                >
                  基本信息
                </button>
                <button
                  className={`px-4 py-2 font-medium ${
                    activeTab === 'chunks'
                      ? 'text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                  onClick={() => setActiveTab('chunks')}
                >
                  文档分块 ({chunks.length})
                </button>
              </div>

              {/* Info Tab */}
              {activeTab === 'info' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm text-gray-500">文件名</label>
                      <p className="font-medium">{document.filename}</p>
                    </div>
                    <div>
                      <label className="text-sm text-gray-500">文件类型</label>
                      <p className="font-medium">
                        {FILE_TYPE_LABELS[`.${document.file_type}`] || document.file_type}
                      </p>
                    </div>
                    <div>
                      <label className="text-sm text-gray-500">文件大小</label>
                      <p className="font-medium">{formatFileSize(document.file_size)}</p>
                    </div>
                    <div>
                      <label className="text-sm text-gray-500">状态</label>
                      <span
                        className={`inline-block px-2 py-1 text-sm rounded ${
                          document.status === 'completed'
                            ? 'bg-green-100 text-green-800'
                            : document.status === 'processing'
                            ? 'bg-blue-100 text-blue-800'
                            : document.status === 'failed'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {DOCUMENT_STATUS_LABELS[document.status]}
                      </span>
                    </div>
                    <div>
                      <label className="text-sm text-gray-500">分块数量</label>
                      <p className="font-medium">{document.chunk_count}</p>
                    </div>
                    <div>
                      <label className="text-sm text-gray-500">Token 数量</label>
                      <p className="font-medium">{document.token_count.toLocaleString()}</p>
                    </div>
                    <div>
                      <label className="text-sm text-gray-500">创建时间</label>
                      <p className="font-medium">{formatDate(document.created_at)}</p>
                    </div>
                    <div>
                      <label className="text-sm text-gray-500">更新时间</label>
                      <p className="font-medium">{formatDate(document.updated_at)}</p>
                    </div>
                  </div>

                  {document.title && (
                    <div>
                      <label className="text-sm text-gray-500">标题</label>
                      <p className="font-medium">{document.title}</p>
                    </div>
                  )}

                  {document.author && (
                    <div>
                      <label className="text-sm text-gray-500">作者</label>
                      <p className="font-medium">{document.author}</p>
                    </div>
                  )}

                  {document.source && (
                    <div>
                      <label className="text-sm text-gray-500">来源</label>
                      <p className="font-medium">{document.source}</p>
                    </div>
                  )}

                  {document.tags.length > 0 && (
                    <div>
                      <label className="text-sm text-gray-500">标签</label>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {document.tags.map((tag, i) => (
                          <span
                            key={i}
                            className="px-2 py-1 bg-gray-100 text-gray-700 text-sm rounded"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {document.status === 'failed' && (
                    <div className="flex gap-2">
                      <button
                        onClick={handleReprocess}
                        disabled={isLoading}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                      >
                        重新处理
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Chunks Tab */}
              {activeTab === 'chunks' && (
                <div className="space-y-4">
                  {chunks.length === 0 ? (
                    <p className="text-gray-500 text-center py-8">暂无分块数据</p>
                  ) : (
                    <div className="space-y-3">
                      {chunks.map((chunk) => (
                        <div
                          key={chunk.id}
                          className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer"
                          onClick={() => setSelectedChunk(selectedChunk?.id === chunk.id ? null : chunk)}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium text-gray-500">
                              分块 #{chunk.chunk_index + 1}
                            </span>
                            <div className="flex items-center gap-2 text-sm text-gray-500">
                              {chunk.page_number && (
                                <span>第 {chunk.page_number} 页</span>
                              )}
                              <span>{chunk.token_count} tokens</span>
                            </div>
                          </div>
                          <p className="text-sm text-gray-700 line-clamp-3">
                            {chunk.content}
                          </p>
                          
                          {selectedChunk?.id === chunk.id && (
                            <div className="mt-4 pt-4 border-t">
                              <div className="flex justify-between items-center mb-2">
                                <span className="text-sm font-medium">完整内容</span>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    copyToClipboard(chunk.content)
                                  }}
                                  className="text-sm text-blue-600 hover:text-blue-800"
                                >
                                  复制
                                </button>
                              </div>
                              <pre className="text-sm bg-gray-50 p-3 rounded overflow-auto max-h-60 whitespace-pre-wrap">
                                {chunk.content}
                              </pre>
                              {chunk.section_title && (
                                <p className="text-sm text-gray-500 mt-2">
                                  章节: {chunk.section_title}
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 p-4 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}

export default DocumentDetail
