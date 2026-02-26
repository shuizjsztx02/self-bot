import { useState } from 'react'
import { Settings, ChevronDown, ChevronUp } from 'lucide-react'

export type SearchMode = 'vector' | 'hybrid' | 'attribution' | 'compression'

export interface AdvancedSearchOptions {
  mode: SearchMode
  topK: number
  useRerank: boolean
  alpha: number
  maxTokens: number
  useHybridForCompression: boolean
}

interface SearchOptionsProps {
  options: AdvancedSearchOptions
  onChange: (options: AdvancedSearchOptions) => void
  hasAnswer?: boolean
  answer?: string
  onAnswerChange?: (answer: string) => void
}

const SEARCH_MODE_LABELS: Record<SearchMode, { label: string; description: string }> = {
  vector: {
    label: '向量检索',
    description: '基于语义相似度的向量搜索',
  },
  hybrid: {
    label: '混合检索',
    description: '向量检索 + BM25关键词检索，使用RRF融合',
  },
  attribution: {
    label: '溯源检索',
    description: '带来源引用和置信度评分的检索',
  },
  compression: {
    label: '压缩检索',
    description: '检索后压缩上下文，优化Token使用',
  },
}

export function SearchOptions({
  options,
  onChange,
  hasAnswer: _hasAnswer = false,
  answer = '',
  onAnswerChange,
}: SearchOptionsProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const updateOption = <K extends keyof AdvancedSearchOptions>(
    key: K,
    value: AdvancedSearchOptions[K]
  ) => {
    onChange({ ...options, [key]: value })
  }

  return (
    <div className="border rounded-lg bg-gray-50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-100 rounded-lg"
      >
        <div className="flex items-center gap-2">
          <Settings className="h-4 w-4 text-gray-500" />
          <span className="font-medium text-gray-700">高级搜索选项</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-gray-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-500" />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 border-t">
          <div className="pt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              搜索模式
            </label>
            <div className="grid grid-cols-2 gap-2">
              {(Object.keys(SEARCH_MODE_LABELS) as SearchMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => updateOption('mode', mode)}
                  className={`p-3 text-left rounded-lg border transition-colors ${
                    options.mode === mode
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-white'
                  }`}
                >
                  <div className="font-medium text-sm">
                    {SEARCH_MODE_LABELS[mode].label}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {SEARCH_MODE_LABELS[mode].description}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                返回结果数
              </label>
              <select
                value={options.topK}
                onChange={(e) => updateOption('topK', parseInt(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </div>

            <div className="flex items-center pt-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.useRerank}
                  onChange={(e) => updateOption('useRerank', e.target.checked)}
                  className="rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-600">启用重排序</span>
              </label>
            </div>
          </div>

          {options.mode === 'hybrid' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                向量检索权重 (alpha): {options.alpha.toFixed(2)}
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={options.alpha}
                onChange={(e) => updateOption('alpha', parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>BM25优先</span>
                <span>向量优先</span>
              </div>
            </div>
          )}

          {options.mode === 'compression' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  最大Token数: {options.maxTokens}
                </label>
                <input
                  type="range"
                  min="500"
                  max="16000"
                  step="500"
                  value={options.maxTokens}
                  onChange={(e) => updateOption('maxTokens', parseInt(e.target.value))}
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>500</span>
                  <span>16000</span>
                </div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.useHybridForCompression}
                  onChange={(e) => updateOption('useHybridForCompression', e.target.checked)}
                  className="rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-600">使用混合检索</span>
              </label>
            </div>
          )}

          {options.mode === 'attribution' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                LLM回答 (用于溯源)
              </label>
              <textarea
                value={answer}
                onChange={(e) => onAnswerChange?.(e.target.value)}
                placeholder="输入LLM生成的回答，系统将分析回答内容的来源..."
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[100px]"
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export const defaultSearchOptions: AdvancedSearchOptions = {
  mode: 'vector',
  topK: 10,
  useRerank: true,
  alpha: 0.5,
  maxTokens: 4000,
  useHybridForCompression: false,
}

export default SearchOptions
