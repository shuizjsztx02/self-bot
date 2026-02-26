import { useState, useCallback, useRef } from 'react'
import { Upload, X, FileText, AlertCircle, CheckCircle } from 'lucide-react'
import { ACCEPTED_FILE_TYPES, FILE_TYPE_LABELS } from '../types/knowledge'

interface FileUploadProgress {
  file: File
  progress: number
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
}

interface DocumentUploaderProps {
  kbId: string
  folderId?: string
  onUploadComplete?: () => void
  onUploadError?: (error: string) => void
  maxFileSize?: number
  maxFiles?: number
}

const DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024
const DEFAULT_MAX_FILES = 10

export default function DocumentUploader({
  kbId,
  folderId,
  onUploadComplete,
  onUploadError,
  maxFileSize = DEFAULT_MAX_FILE_SIZE,
  maxFiles = DEFAULT_MAX_FILES,
}: DocumentUploaderProps) {
  const [files, setFiles] = useState<FileUploadProgress[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = useCallback((file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_FILE_TYPES.includes(ext as any)) {
      return `不支持的文件类型: ${ext}`
    }
    if (file.size > maxFileSize) {
      return `文件大小超过限制: ${(maxFileSize / 1024 / 1024).toFixed(0)}MB`
    }
    return null
  }, [maxFileSize])

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const fileArray = Array.from(newFiles)
    const validFiles: FileUploadProgress[] = []

    for (const file of fileArray) {
      if (files.length + validFiles.length >= maxFiles) break
      const error = validateFile(file)
      validFiles.push({
        file,
        progress: 0,
        status: error ? 'error' : 'pending',
        error: error || undefined,
      })
    }

    setFiles((prev) => [...prev, ...validFiles])
  }, [files.length, maxFiles, validateFile])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files)
    }
  }, [addFiles])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files)
      e.target.value = ''
    }
  }, [addFiles])

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const clearFiles = useCallback(() => {
    setFiles([])
  }, [])

  const uploadFiles = useCallback(async () => {
    const pendingFiles = files.filter((f) => f.status === 'pending')
    if (pendingFiles.length === 0) return

    setIsUploading(true)
    const token = localStorage.getItem('token')
    let hasError = false

    for (const fileProgress of pendingFiles) {
      const index = files.findIndex((f) => f.file === fileProgress.file)
      if (index === -1) continue

      setFiles((prev) => {
        const updated = [...prev]
        updated[index] = { ...updated[index], status: 'uploading', progress: 0 }
        return updated
      })

      try {
        const formData = new FormData()
        formData.append('kb_id', kbId)
        formData.append('file', fileProgress.file)
        if (folderId) {
          formData.append('folder_id', folderId)
        }

        const xhr = new XMLHttpRequest()
        
        await new Promise<void>((resolve, reject) => {
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              const progress = Math.round((e.loaded / e.total) * 100)
              setFiles((prev) => {
                const updated = [...prev]
                updated[index] = { ...updated[index], progress }
                return updated
              })
            }
          }

          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve()
            } else {
              try {
                const response = JSON.parse(xhr.responseText)
                reject(new Error(response.detail || '上传失败'))
              } catch {
                reject(new Error('上传失败'))
              }
            }
          }

          xhr.onerror = () => reject(new Error('网络错误'))

          xhr.open('POST', '/api/documents/upload')
          if (token) {
            xhr.setRequestHeader('Authorization', `Bearer ${token}`)
          }
          xhr.send(formData)
        })

        setFiles((prev) => {
          const updated = [...prev]
          updated[index] = { ...updated[index], status: 'success', progress: 100 }
          return updated
        })
      } catch (e: any) {
        hasError = true
        const errorMsg = e.message || '上传失败'
        setFiles((prev) => {
          const updated = [...prev]
          updated[index] = { ...updated[index], status: 'error', error: errorMsg }
          return updated
        })
        onUploadError?.(errorMsg)
      }
    }

    setIsUploading(false)
    if (!hasError) {
      onUploadComplete?.()
    }
  }, [files, kbId, folderId, onUploadComplete, onUploadError])

  const getFileTypeIcon = (filename: string) => {
    const ext = '.' + filename.split('.').pop()?.toLowerCase()
    return FILE_TYPE_LABELS[ext] || '文件'
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  return (
    <div className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors duration-200
          ${isDragOver 
            ? 'border-blue-500 bg-blue-50' 
            : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_FILE_TYPES.join(',')}
          onChange={handleFileSelect}
          className="hidden"
        />
        <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
        <p className="text-gray-600 mb-2">
          拖拽文件到此处，或点击选择文件
        </p>
        <p className="text-sm text-gray-400">
          支持的格式: Markdown, PDF, Word, PowerPoint, Excel, TXT
        </p>
        <p className="text-xs text-gray-400 mt-1">
          单个文件最大 {(maxFileSize / 1024 / 1024).toFixed(0)}MB，最多 {maxFiles} 个文件
        </p>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">
              已选择 {files.length} 个文件
            </span>
            <button
              onClick={clearFiles}
              disabled={isUploading}
              className="text-sm text-red-500 hover:text-red-600 disabled:text-gray-400"
            >
              清空
            </button>
          </div>

          <div className="max-h-60 overflow-y-auto space-y-2">
            {files.map((fileProgress, index) => (
              <div
                key={`${fileProgress.file.name}-${index}`}
                className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
              >
                <FileText className="h-5 w-5 text-gray-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium truncate">
                      {fileProgress.file.name}
                    </span>
                    <span className="text-xs text-gray-400 ml-2">
                      {formatFileSize(fileProgress.file.size)}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500">
                    {getFileTypeIcon(fileProgress.file.name)}
                  </div>
                  {fileProgress.status === 'uploading' && (
                    <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 transition-all duration-300"
                        style={{ width: `${fileProgress.progress}%` }}
                      />
                    </div>
                  )}
                  {fileProgress.status === 'error' && (
                    <div className="mt-1 text-xs text-red-500 flex items-center gap-1">
                      <AlertCircle className="h-3 w-3" />
                      {fileProgress.error}
                    </div>
                  )}
                </div>
                {fileProgress.status === 'success' ? (
                  <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                ) : fileProgress.status !== 'uploading' ? (
                  <button
                    onClick={() => removeFile(index)}
                    disabled={isUploading}
                    className="p-1 hover:bg-gray-200 rounded disabled:opacity-50"
                  >
                    <X className="h-4 w-4 text-gray-400" />
                  </button>
                ) : null}
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={clearFiles}
              disabled={isUploading}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 disabled:opacity-50"
            >
              取消
            </button>
            <button
              onClick={uploadFiles}
              disabled={isUploading || files.every((f) => f.status !== 'pending')}
              className="px-4 py-2 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isUploading ? '上传中...' : `上传 ${files.filter((f) => f.status === 'pending').length} 个文件`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
