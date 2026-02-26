import { useState, useEffect } from 'react'
import knowledgeApi from '../services/knowledgeApi'
import type { KBPermission } from '../types/knowledge'
import { KB_ROLE_LABELS, type KBRole } from '../types/knowledge'
import { getErrorMessage } from '../utils/errorHandler'

interface PermissionManagerProps {
  kbId: string
  open: boolean
  onClose: () => void
}

export function PermissionManager({ kbId, open, onClose }: PermissionManagerProps) {
  const [permissions, setPermissions] = useState<KBPermission[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newUserId, setNewUserId] = useState('')
  const [newRole, setNewRole] = useState<KBRole>('viewer')
  const [newExpiresAt, setNewExpiresAt] = useState('')

  useEffect(() => {
    if (open && kbId) {
      fetchPermissions()
    }
  }, [open, kbId])

  const fetchPermissions = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await knowledgeApi.getPermissions(kbId)
      setPermissions(data)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleGrantPermission = async () => {
    if (!newUserId.trim()) {
      setError('请输入用户ID')
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      await knowledgeApi.grantPermission(kbId, {
        user_id: newUserId.trim(),
        role: newRole,
        expires_at: newExpiresAt || undefined,
      })
      setNewUserId('')
      setNewRole('viewer')
      setNewExpiresAt('')
      setShowAddForm(false)
      fetchPermissions()
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleRevokePermission = async (permissionId: string) => {
    if (!confirm('确定要撤销此权限吗？')) return

    setIsLoading(true)
    setError(null)
    try {
      await knowledgeApi.revokePermission(kbId, permissionId)
      setPermissions(permissions.filter((p) => p.id !== permissionId))
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '永久'
    return new Date(dateStr).toLocaleString('zh-CN')
  }

  const isExpired = (expiresAt: string | null) => {
    if (!expiresAt) return false
    return new Date(expiresAt) < new Date()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">权限管理</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {error && (
            <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-4">
              {error}
            </div>
          )}

          {/* Add Permission Button */}
          {!showAddForm && (
            <button
              onClick={() => setShowAddForm(true)}
              className="mb-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              添加权限
            </button>
          )}

          {/* Add Permission Form */}
          {showAddForm && (
            <div className="bg-gray-50 p-4 rounded-lg mb-4">
              <h3 className="font-medium mb-3">添加新权限</h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-gray-500 mb-1">用户ID</label>
                  <input
                    type="text"
                    value={newUserId}
                    onChange={(e) => setNewUserId(e.target.value)}
                    placeholder="输入用户ID"
                    className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-500 mb-1">角色</label>
                  <select
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value as KBRole)}
                    className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="viewer">{KB_ROLE_LABELS.viewer}</option>
                    <option value="editor">{KB_ROLE_LABELS.editor}</option>
                    <option value="admin">{KB_ROLE_LABELS.admin}</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-500 mb-1">过期时间（可选）</label>
                  <input
                    type="datetime-local"
                    value={newExpiresAt}
                    onChange={(e) => setNewExpiresAt(e.target.value)}
                    className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleGrantPermission}
                    disabled={isLoading}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    确认添加
                  </button>
                  <button
                    onClick={() => {
                      setShowAddForm(false)
                      setNewUserId('')
                      setNewRole('viewer')
                      setNewExpiresAt('')
                    }}
                    className="px-4 py-2 text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
                  >
                    取消
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Permissions List */}
          {isLoading && permissions.length === 0 ? (
            <div className="flex items-center justify-center h-40">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : permissions.length === 0 ? (
            <p className="text-gray-500 text-center py-8">暂无权限记录</p>
          ) : (
            <div className="space-y-3">
              {permissions.map((permission) => (
                <div
                  key={permission.id}
                  className={`border rounded-lg p-4 ${
                    isExpired(permission.expires_at) ? 'bg-gray-100 opacity-60' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium">
                          用户: {permission.user_id || `组: ${permission.group_id}`}
                        </span>
                        <span
                          className={`px-2 py-0.5 text-xs rounded ${
                            permission.role === 'owner'
                              ? 'bg-purple-100 text-purple-800'
                              : permission.role === 'admin'
                              ? 'bg-red-100 text-red-800'
                              : permission.role === 'editor'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {KB_ROLE_LABELS[permission.role]}
                        </span>
                        {isExpired(permission.expires_at) && (
                          <span className="px-2 py-0.5 text-xs rounded bg-red-100 text-red-800">
                            已过期
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-gray-500">
                        <span>授权时间: {formatDate(permission.granted_at)}</span>
                        {permission.expires_at && (
                          <span className="ml-4">
                            过期时间: {formatDate(permission.expires_at)}
                          </span>
                        )}
                      </div>
                    </div>
                    {permission.role !== 'owner' && (
                      <button
                        onClick={() => handleRevokePermission(permission.id)}
                        disabled={isLoading || isExpired(permission.expires_at)}
                        className="px-3 py-1 text-sm text-red-600 hover:text-red-800 hover:bg-red-50 rounded disabled:opacity-50"
                      >
                        撤销
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
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

export default PermissionManager
