import { useState, useEffect } from 'react'
import { X, Save, Loader2 } from 'lucide-react'
import type { KnowledgeBase, KnowledgeBaseCreate } from '../types/knowledge'

interface KnowledgeBaseFormProps {
  knowledgeBase?: KnowledgeBase
  onSubmit: (data: KnowledgeBaseCreate) => Promise<void>
  onCancel: () => void
  isLoading?: boolean
}

const EMBEDDING_MODELS = [
  { value: 'text-embedding-ada-002', label: 'OpenAI Ada-002' },
  { value: 'text-embedding-3-small', label: 'OpenAI Embedding-3 Small' },
  { value: 'text-embedding-3-large', label: 'OpenAI Embedding-3 Large' },
  { value: 'bge-large-zh-v1.5', label: 'BGE Large Chinese' },
  { value: 'bge-m3', label: 'BGE M3' },
] as const

const DEFAULT_CHUNK_SIZE = 500
const DEFAULT_CHUNK_OVERLAP = 50

export default function KnowledgeBaseForm({
  knowledgeBase,
  onSubmit,
  onCancel,
  isLoading = false,
}: KnowledgeBaseFormProps) {
  const [formData, setFormData] = useState<KnowledgeBaseCreate>({
    name: '',
    description: '',
    embedding_model: EMBEDDING_MODELS[0].value,
    chunk_size: DEFAULT_CHUNK_SIZE,
    chunk_overlap: DEFAULT_CHUNK_OVERLAP,
    department: '',
    security_level: 1,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})

  const isEditing = !!knowledgeBase

  useEffect(() => {
    if (knowledgeBase) {
      setFormData({
        name: knowledgeBase.name,
        description: knowledgeBase.description || '',
        embedding_model: knowledgeBase.embedding_model,
        chunk_size: knowledgeBase.chunk_size,
        chunk_overlap: knowledgeBase.chunk_overlap,
        department: knowledgeBase.department || '',
        security_level: knowledgeBase.security_level,
      })
    }
  }, [knowledgeBase])

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!formData.name.trim()) {
      newErrors.name = '知识库名称不能为空'
    } else if (formData.name.length > 100) {
      newErrors.name = '名称不能超过100个字符'
    }

    if (formData.description && formData.description.length > 500) {
      newErrors.description = '描述不能超过500个字符'
    }

    const chunkSize = formData.chunk_size ?? DEFAULT_CHUNK_SIZE
    const chunkOverlap = formData.chunk_overlap ?? DEFAULT_CHUNK_OVERLAP
    const securityLevel = formData.security_level ?? 1

    if (chunkSize < 100 || chunkSize > 2000) {
      newErrors.chunk_size = '分块大小应在100-2000之间'
    }

    if (chunkOverlap < 0 || chunkOverlap >= chunkSize) {
      newErrors.chunk_overlap = '分块重叠应小于分块大小'
    }

    if (securityLevel < 1 || securityLevel > 5) {
      newErrors.security_level = '安全等级应在1-5之间'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validateForm()) return

    const submitData = isEditing
      ? {
          name: formData.name,
          description: formData.description || undefined,
          embedding_model: formData.embedding_model,
          chunk_size: formData.chunk_size,
          chunk_overlap: formData.chunk_overlap,
          department: formData.department || undefined,
          security_level: formData.security_level,
        }
      : formData

    await onSubmit(submitData)
  }

  const updateField = <K extends keyof KnowledgeBaseCreate>(
    field: K,
    value: KnowledgeBaseCreate[K]
  ) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev }
        delete next[field]
        return next
      })
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">
            {isEditing ? '编辑知识库' : '创建知识库'}
          </h2>
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => updateField('name', e.target.value)}
              disabled={isLoading}
              className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.name ? 'border-red-500' : 'border-gray-300'
              }`}
              placeholder="输入知识库名称"
            />
            {errors.name && (
              <p className="mt-1 text-sm text-red-500">{errors.name}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              描述
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => updateField('description', e.target.value)}
              disabled={isLoading}
              rows={3}
              className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.description ? 'border-red-500' : 'border-gray-300'
              }`}
              placeholder="输入知识库描述（可选）"
            />
            {errors.description && (
              <p className="mt-1 text-sm text-red-500">{errors.description}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              嵌入模型
            </label>
            <select
              value={formData.embedding_model}
              onChange={(e) => updateField('embedding_model', e.target.value)}
              disabled={isLoading || isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
            >
              {EMBEDDING_MODELS.map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label}
                </option>
              ))}
            </select>
            {isEditing && (
              <p className="mt-1 text-xs text-gray-500">
                嵌入模型创建后不可修改
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                分块大小
              </label>
              <input
                type="number"
                value={formData.chunk_size}
                onChange={(e) => updateField('chunk_size', parseInt(e.target.value) || 0)}
                disabled={isLoading}
                min={100}
                max={2000}
                className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  errors.chunk_size ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.chunk_size && (
                <p className="mt-1 text-sm text-red-500">{errors.chunk_size}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                分块重叠
              </label>
              <input
                type="number"
                value={formData.chunk_overlap}
                onChange={(e) => updateField('chunk_overlap', parseInt(e.target.value) || 0)}
                disabled={isLoading}
                min={0}
                className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  errors.chunk_overlap ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.chunk_overlap && (
                <p className="mt-1 text-sm text-red-500">{errors.chunk_overlap}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                部门
              </label>
              <input
                type="text"
                value={formData.department}
                onChange={(e) => updateField('department', e.target.value)}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="所属部门（可选）"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                安全等级
              </label>
              <select
                value={formData.security_level}
                onChange={(e) => updateField('security_level', parseInt(e.target.value))}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {[1, 2, 3, 4, 5].map((level) => (
                  <option key={level} value={level}>
                    等级 {level}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-400 flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  保存中...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  {isEditing ? '保存修改' : '创建知识库'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
