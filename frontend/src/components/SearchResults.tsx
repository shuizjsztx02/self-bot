import { useState } from 'react'
import { FileText, ChevronDown, ChevronRight, ExternalLink, Copy, Check } from 'lucide-react'
import type { SearchResult } from '../types/knowledge'

interface SearchResultsProps {
  results: SearchResult[]
  searchTimeMs?: number
  isLoading?: boolean
  onResultClick?: (result: SearchResult) => void
}

export default function SearchResults({
  results,
  searchTimeMs,
  isLoading = false,
  onResultClick,
}: SearchResultsProps) {
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set())
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const toggleExpand = (chunkId: string) => {
    setExpandedResults((prev) => {
      const next = new Set(prev)
      if (next.has(chunkId)) {
        next.delete(chunkId)
      } else {
        next.add(chunkId)
      }
      return next
    })
  }

  const copyContent = async (content: string, chunkId: string) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedId(chunkId)
      setTimeout(() => setCopiedId(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600 bg-green-50'
    if (score >= 0.6) return 'text-blue-600 bg-blue-50'
    if (score >= 0.4) return 'text-yellow-600 bg-yellow-50'
    return 'text-gray-600 bg-gray-50'
  }

  const getScoreLabel = (score: number) => {
    if (score >= 0.8) return '高度相关'
    if (score >= 0.6) return '较为相关'
    if (score >= 0.4) return '部分相关'
    return '低相关'
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse">
            <div className="p-4 border rounded-lg">
              <div className="flex justify-between mb-2">
                <div className="h-4 bg-gray-200 rounded w-1/3" />
                <div className="h-4 bg-gray-200 rounded w-16" />
              </div>
              <div className="space-y-2">
                <div className="h-3 bg-gray-200 rounded w-full" />
                <div className="h-3 bg-gray-200 rounded w-5/6" />
                <div className="h-3 bg-gray-200 rounded w-4/6" />
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
        <p>暂无搜索结果</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {searchTimeMs !== undefined && (
        <div className="text-sm text-gray-500 mb-2">
          找到 {results.length} 个结果，耗时 {searchTimeMs}ms
        </div>
      )}

      {results.map((result, index) => {
        const isExpanded = expandedResults.has(result.chunk_id)
        const showExpandButton = result.content.length > 300

        return (
          <div
            key={`${result.chunk_id}-${index}`}
            className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow"
          >
            <div className="p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <FileText className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <span className="font-medium text-blue-600 truncate">
                      {result.doc_name}
                    </span>
                    {result.page_number && (
                      <span className="text-xs text-gray-400 flex-shrink-0">
                        第 {result.page_number} 页
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500">
                    知识库: {result.kb_name}
                    {result.section_title && ` · ${result.section_title}`}
                  </div>
                </div>
                <div className={`flex-shrink-0 ml-3 px-2 py-1 rounded text-xs font-medium ${getScoreColor(result.score)}`}>
                  {getScoreLabel(result.score)}
                </div>
              </div>

              <div className="relative">
                <p className={`text-sm text-gray-700 leading-relaxed ${!isExpanded && showExpandButton ? 'line-clamp-3' : ''}`}>
                  {result.content}
                </p>
                {showExpandButton && (
                  <button
                    onClick={() => toggleExpand(result.chunk_id)}
                    className="mt-2 text-sm text-blue-500 hover:text-blue-600 flex items-center gap-1"
                  >
                    {isExpanded ? (
                      <>
                        <ChevronDown className="h-4 w-4" />
                        收起
                      </>
                    ) : (
                      <>
                        <ChevronRight className="h-4 w-4" />
                        展开全文
                      </>
                    )}
                  </button>
                )}
              </div>

              {result.extra_data && Object.keys(result.extra_data).length > 0 && (
                <div className="mt-3 pt-3 border-t">
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(result.extra_data).map(([key, value]) => (
                      <span
                        key={key}
                        className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded"
                      >
                        {key}: {String(value)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-3 flex items-center justify-between">
                <div className="text-xs text-gray-400">
                  相似度: {(result.score * 100).toFixed(1)}%
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => copyContent(result.content, result.chunk_id)}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                  >
                    {copiedId === result.chunk_id ? (
                      <>
                        <Check className="h-3 w-3" />
                        已复制
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" />
                        复制
                      </>
                    )}
                  </button>
                  {onResultClick && (
                    <button
                      onClick={() => onResultClick(result)}
                      className="text-xs text-blue-500 hover:text-blue-600 flex items-center gap-1"
                    >
                      <ExternalLink className="h-3 w-3" />
                      查看原文
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
