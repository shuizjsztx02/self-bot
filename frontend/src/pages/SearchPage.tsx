import { useKnowledgeStore } from '../stores/knowledgeStore'
import { useState, useEffect } from 'react'
import { Search as SearchIcon, Filter, Sparkles, FileText, Zap } from 'lucide-react'
import SearchResults from '../components/SearchResults'
import SearchOptions, { 
  SearchMode, 
  AdvancedSearchOptions, 
  defaultSearchOptions 
} from '../components/SearchOptions'
import knowledgeApi from '../services/knowledgeApi'

interface RAGResponse {
  query: string
  answer: string
  sources: Array<{
    chunk_id: string
    doc_id: string
    doc_name: string
    content: string
    score: number
    relevance: number
    citation: string
  }>
  overall_confidence: number
  rewritten_query: string | null
  search_time_ms: number
}

interface CompressionSearchResponse {
  query: string
  compressed_context: string
  documents: Array<{
    id: string
    original_content: string
    compressed_content: string
    relevance_score: number
    token_count: number
  }>
  total_original_tokens: number
  total_compressed_tokens: number
  compression_ratio: number
}

export default function SearchPage() {
  const { 
    knowledgeBases, 
    searchResults, 
    isSearching, 
    searchTimeMs,
    error, 
    search,
    fetchKnowledgeBases 
  } = useKnowledgeStore()
  
  const [query, setQuery] = useState('')
  const [selectedKB, setSelectedKB] = useState<string>('')
  const [showFilters, setShowFilters] = useState(false)
  const [searchOptions, setSearchOptions] = useState<AdvancedSearchOptions>(defaultSearchOptions)
  const [answer, setAnswer] = useState('')
  
  const [ragResponse, setRagResponse] = useState<RAGResponse | null>(null)
  const [compressionResponse, setCompressionResponse] = useState<CompressionSearchResponse | null>(null)

  useEffect(() => {
    fetchKnowledgeBases()
  }, [fetchKnowledgeBases])

  const handleSearch = async () => {
    if (!query.trim()) return
    
    setRagResponse(null)
    setCompressionResponse(null)
    
    const kbId = selectedKB || (knowledgeBases.length > 0 ? knowledgeBases[0].id : '')
    if (!kbId) {
      return
    }

    try {
      if (searchOptions.mode === 'hybrid') {
        await search(
          query.trim(),
          [kbId],
          { 
            top_k: searchOptions.topK,
            use_rerank: searchOptions.useRerank,
          }
        )
      } else if (searchOptions.mode === 'attribution') {
        const response = await knowledgeApi.searchWithAttribution({
          query: query.trim(),
          kb_id: kbId,
          answer: answer || '这是一个示例回答，用于溯源分析。',
          top_k: searchOptions.topK,
          use_rerank: searchOptions.useRerank,
        })
        setRagResponse(response)
      } else if (searchOptions.mode === 'compression') {
        const response = await knowledgeApi.searchWithCompression({
          query: query.trim(),
          kb_id: kbId,
          top_k: searchOptions.topK,
          max_tokens: searchOptions.maxTokens,
          use_hybrid: searchOptions.useHybridForCompression,
        })
        setCompressionResponse(response)
      } else {
        await search(
          query.trim(),
          selectedKB ? [selectedKB] : undefined,
          { 
            top_k: searchOptions.topK,
            use_rerank: searchOptions.useRerank,
          }
        )
      }
    } catch (e) {
      console.error('Search error:', e)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSearch()
    }
  }

  const getModeIcon = (mode: SearchMode) => {
    switch (mode) {
      case 'hybrid': return <Zap className="h-4 w-4" />
      case 'attribution': return <Sparkles className="h-4 w-4" />
      case 'compression': return <FileText className="h-4 w-4" />
      default: return <SearchIcon className="h-4 w-4" />
    }
  }

  const renderAttributionResults = () => {
    if (!ragResponse) return null
    
    return (
      <div className="space-y-6">
        <div className="bg-blue-50 rounded-lg p-4">
          <h3 className="font-medium text-blue-800 mb-2">回答</h3>
          <p className="text-gray-700">{ragResponse.answer}</p>
          <div className="mt-3 flex items-center gap-4 text-sm">
            <span className="text-blue-600">
              置信度: {(ragResponse.overall_confidence * 100).toFixed(1)}%
            </span>
            <span className="text-gray-500">
              耗时: {ragResponse.search_time_ms.toFixed(0)}ms
            </span>
          </div>
        </div>
        
        <div>
          <h3 className="font-medium text-gray-700 mb-3">来源引用 ({ragResponse.sources.length})</h3>
          <div className="space-y-3">
            {ragResponse.sources.map((source, index) => (
              <div key={source.chunk_id} className="border rounded-lg p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-500">
                    来源 #{index + 1}
                  </span>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-blue-600">相关度: {(source.relevance * 100).toFixed(1)}%</span>
                    <span className="text-gray-500">评分: {source.score.toFixed(3)}</span>
                  </div>
                </div>
                <p className="text-sm text-gray-700 line-clamp-3">{source.content}</p>
                <div className="mt-2 text-xs text-gray-500">
                  文档: {source.doc_name} | 引用: {source.citation}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const renderCompressionResults = () => {
    if (!compressionResponse) return null
    
    return (
      <div className="space-y-6">
        <div className="bg-green-50 rounded-lg p-4">
          <h3 className="font-medium text-green-800 mb-2">压缩上下文</h3>
          <div className="text-sm text-gray-600 mb-3">
            原始Token: {compressionResponse.total_original_tokens} → 
            压缩后: {compressionResponse.total_compressed_tokens} 
            (压缩率: {(compressionResponse.compression_ratio * 100).toFixed(1)}%)
          </div>
          <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-white p-3 rounded border max-h-60 overflow-auto">
            {compressionResponse.compressed_context}
          </pre>
        </div>
        
        <div>
          <h3 className="font-medium text-gray-700 mb-3">压缩文档 ({compressionResponse.documents.length})</h3>
          <div className="space-y-3">
            {compressionResponse.documents.map((doc, index) => (
              <div key={doc.id} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-500">文档 #{index + 1}</span>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-green-600">相关度: {(doc.relevance_score * 100).toFixed(1)}%</span>
                    <span className="text-gray-500">Token: {doc.token_count}</span>
                  </div>
                </div>
                <div className="text-sm text-gray-700 line-clamp-3">
                  {doc.compressed_content}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="border-b bg-white px-6 py-4">
        <h1 className="text-2xl font-bold mb-4">知识库搜索</h1>
        
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入搜索内容，按 Enter 搜索..."
              className="w-full pl-10 pr-4 py-2.5 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <select
            value={selectedKB}
            onChange={(e) => setSelectedKB(e.target.value)}
            className="px-4 py-2.5 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[150px]"
          >
            <option value="">全部知识库</option>
            {knowledgeBases.map((kb) => (
              <option key={kb.id} value={kb.id}>
                {kb.name}
              </option>
            ))}
          </select>
          
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`px-3 py-2.5 border rounded-lg hover:bg-gray-50 ${
              showFilters ? 'bg-gray-100' : ''
            }`}
            title="筛选选项"
          >
            <Filter className="h-5 w-5 text-gray-500" />
          </button>
          
          <button
            onClick={handleSearch}
            disabled={isSearching || !query.trim()}
            className="px-6 py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {getModeIcon(searchOptions.mode)}
            {isSearching ? '搜索中...' : '搜索'}
          </button>
        </div>

        {showFilters && (
          <div className="mt-4">
            <SearchOptions
              options={searchOptions}
              onChange={setSearchOptions}
              hasAnswer={searchOptions.mode === 'attribution'}
              answer={answer}
              onAnswerChange={setAnswer}
            />
          </div>
        )}
      </div>

      <div className="flex-1 p-6 overflow-y-auto">
        {error && (
          <div className="mb-4 p-4 bg-red-50 text-red-600 rounded-lg">
            搜索错误: {error}
          </div>
        )}

        {searchOptions.mode === 'attribution' && ragResponse ? (
          renderAttributionResults()
        ) : searchOptions.mode === 'compression' && compressionResponse ? (
          renderCompressionResults()
        ) : (
          <>
            {query.trim() && searchResults.length === 0 && !isSearching ? (
              <div className="text-center py-12 text-gray-500">
                未找到相关内容，请尝试其他关键词
              </div>
            ) : (
              <SearchResults
                results={searchResults}
                searchTimeMs={searchTimeMs}
                isLoading={isSearching}
              />
            )}
          </>
        )}
      </div>
    </div>
  )
}
