import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, MessageSquare, User as UserIcon, Shield, ToggleLeft, ToggleRight, Plus, Trash2, Database, Edit2 } from 'lucide-react'
import { knowledgeApi } from '../services/knowledgeApi'
import { getErrorMessage } from '../utils/errorHandler'
import Sidebar from '../components/Sidebar'
import { toast } from '../components/Toast'
import type { UserDetail, PermissionInfo, KnowledgeBase } from '../types/knowledge'
import { USER_LEVEL_LABELS } from '../types/knowledge'

export default function UserDetailPage() {
  const { userId } = useParams<{ userId: string }>()
  const navigate = useNavigate()
  
  const [user, setUser] = useState<UserDetail | null>(null)
  const [permissions, setPermissions] = useState<PermissionInfo[]>([])
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showLevelModal, setShowLevelModal] = useState(false)
  const [showDepartmentModal, setShowDepartmentModal] = useState(false)
  const [showPermissionModal, setShowPermissionModal] = useState(false)
  const [selectedLevel, setSelectedLevel] = useState(1)
  const [department, setDepartment] = useState('')
  const [isUpdating, setIsUpdating] = useState(false)
  const [newPermission, setNewPermission] = useState({
    kb_id: '',
    role: 'viewer',
  })

  useEffect(() => {
    if (userId) {
      fetchUser()
      fetchPermissions()
      fetchKnowledgeBases()
    }
  }, [userId])

  const fetchUser = async () => {
    if (!userId) return
    
    setIsLoading(true)
    setError(null)
    try {
      const data = await knowledgeApi.getUser(userId)
      setUser(data)
      setSelectedLevel(data.level)
      setDepartment(data.department || '')
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const fetchPermissions = async () => {
    if (!userId) return
    
    try {
      const data = await knowledgeApi.getUserPermissions(userId)
      setPermissions(data.items)
    } catch (e) {
      console.error('Failed to fetch permissions:', e)
    }
  }

  const fetchKnowledgeBases = async () => {
    try {
      const data = await knowledgeApi.listKnowledgeBases()
      setKnowledgeBases(data)
    } catch (e) {
      console.error('Failed to fetch knowledge bases:', e)
    }
  }

  const handleUpdateLevel = async () => {
    if (!userId || !user) return
    
    setIsUpdating(true)
    try {
      const updated = await knowledgeApi.updateUserLevel(userId, selectedLevel)
      setUser(updated)
      setShowLevelModal(false)
      toast.success('修改成功', `用户级别已更新为 L${selectedLevel}`)
    } catch (e) {
      toast.error('修改失败', getErrorMessage(e))
    } finally {
      setIsUpdating(false)
    }
  }

  const handleUpdateDepartment = async () => {
    if (!userId || !user) return
    
    setIsUpdating(true)
    try {
      const updated = await knowledgeApi.updateUser(userId, { department: department || null })
      setUser(updated)
      setShowDepartmentModal(false)
      toast.success('修改成功', `部门已更新为 "${department || '未设置'}"`)
    } catch (e) {
      toast.error('修改失败', getErrorMessage(e))
    } finally {
      setIsUpdating(false)
    }
  }

  const handleToggleStatus = async () => {
    if (!userId || !user) return
    
    const newStatus = !user.is_active
    const action = newStatus ? '启用' : '禁用'
    
    if (!confirm(`确定要${action}用户 "${user.name}" 吗？`)) return
    
    setIsUpdating(true)
    try {
      const updated = await knowledgeApi.updateUserStatus(userId, newStatus)
      setUser(updated)
      toast.success('操作成功', `用户已${action}`)
    } catch (e) {
      toast.error('操作失败', getErrorMessage(e))
    } finally {
      setIsUpdating(false)
    }
  }

  const handleToggleSuperuser = async () => {
    if (!userId || !user) return
    
    const newStatus = !user.is_superuser
    const action = newStatus ? '设置为超级用户' : '取消超级用户权限'
    
    if (!confirm(`确定要${action} "${user.name}" 吗？`)) return
    
    setIsUpdating(true)
    try {
      const updated = await knowledgeApi.updateUserSuperuser(userId, newStatus)
      setUser(updated)
      toast.success('操作成功', `已${action}`)
    } catch (e) {
      toast.error('操作失败', getErrorMessage(e))
    } finally {
      setIsUpdating(false)
    }
  }

  const handleGrantPermission = async () => {
    if (!userId || !newPermission.kb_id) {
      toast.error('验证失败', '请选择知识库')
      return
    }
    
    setIsUpdating(true)
    try {
      await knowledgeApi.grantUserPermission(userId, {
        kb_id: newPermission.kb_id,
        role: newPermission.role,
      })
      toast.success('授权成功', '权限已授予')
      setShowPermissionModal(false)
      setNewPermission({ kb_id: '', role: 'viewer' })
      fetchPermissions()
    } catch (e) {
      toast.error('授权失败', getErrorMessage(e))
    } finally {
      setIsUpdating(false)
    }
  }

  const handleRevokePermission = async (permission: PermissionInfo) => {
    if (!userId) return
    
    if (!confirm(`确定要撤销用户对 "${permission.kb_name}" 的 ${permission.role} 权限吗？`)) return
    
    setIsUpdating(true)
    try {
      await knowledgeApi.revokeUserPermission(userId, permission.id)
      toast.success('撤销成功', '权限已撤销')
      fetchPermissions()
    } catch (e) {
      toast.error('撤销失败', getErrorMessage(e))
    } finally {
      setIsUpdating(false)
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('zh-CN')
  }

  const getLevelBadgeColor = (level: number) => {
    switch (level) {
      case 4:
        return 'bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300'
      case 3:
        return 'bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300'
      case 2:
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300'
      default:
        return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
    }
  }

  const getRoleBadgeColor = (role: string) => {
    switch (role.toLowerCase()) {
      case 'owner':
        return 'bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300'
      case 'admin':
        return 'bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300'
      case 'editor':
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300'
      default:
        return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
    }
  }

  const getRoleLabel = (role: string) => {
    const labels: Record<string, string> = {
      owner: '所有者',
      admin: '管理员',
      editor: '编辑者',
      viewer: '查看者',
    }
    return labels[role.toLowerCase()] || role
  }

  const getLevelDescription = (level: number) => {
    switch (level) {
      case 4:
        return '可创建无限知识库，可被授予所有角色'
      case 3:
        return '可创建10个知识库，可管理权限'
      case 2:
        return '可创建5个知识库，可编辑文档'
      default:
        return '可创建1个知识库，只能查看'
    }
  }

  const existingKbIds = permissions.map(p => p.kb_id)
  const availableKnowledgeBases = knowledgeBases.filter(kb => !existingKbIds.includes(kb.id))

  if (isLoading && !user) {
    return (
      <div className="flex h-screen bg-slate-100 dark:bg-slate-900">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="flex h-screen bg-slate-100 dark:bg-slate-900">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-gray-500 dark:text-slate-400">用户不存在</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-slate-100 dark:bg-slate-900">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="border-b bg-white px-6 py-4 dark:bg-slate-800 dark:border-slate-700">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-2 text-gray-600 hover:text-primary-600 transition-colors dark:text-slate-400 dark:hover:text-primary-400"
              title="返回聊天"
            >
              <MessageSquare className="h-5 w-5" />
              <span className="text-sm font-medium">返回聊天</span>
            </button>
            <div className="h-6 w-px bg-gray-200 dark:bg-slate-600" />
            <button
              onClick={() => navigate('/users')}
              className="flex items-center gap-2 text-gray-600 hover:text-primary-600 transition-colors dark:text-slate-400 dark:hover:text-primary-400"
            >
              <ArrowLeft className="h-5 w-5" />
              <span className="text-sm font-medium">返回用户列表</span>
            </button>
            <div className="h-6 w-px bg-gray-200 dark:bg-slate-600" />
            <div className="flex items-center gap-2">
              <UserIcon className="h-6 w-6 text-blue-500" />
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">用户详情</h1>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-4 bg-red-50 text-red-600 rounded-lg dark:bg-red-900/30 dark:text-red-400">
              {error}
            </div>
          )}

          <div className="max-w-4xl mx-auto space-y-6">
            <div className="bg-white rounded-lg shadow p-6 dark:bg-slate-800">
              <h2 className="text-lg font-semibold mb-4 dark:text-white">基本信息</h2>
              
              <div className="flex items-start gap-6">
                <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/30">
                  <span className="text-3xl text-primary-600 font-medium dark:text-primary-400">
                    {user.name.charAt(0).toUpperCase()}
                  </span>
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl font-bold dark:text-white">{user.name}</span>
                    {user.is_superuser && (
                      <span className="px-2 py-1 text-xs rounded bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300">
                        超级用户
                      </span>
                    )}
                    {user.is_active ? (
                      <span className="px-2 py-1 text-xs rounded bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300">
                        已激活
                      </span>
                    ) : (
                      <span className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                        已禁用
                      </span>
                    )}
                  </div>
                  <div className="text-gray-500 dark:text-slate-400">{user.email}</div>
                </div>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">部门</label>
                  <div className="flex items-center gap-2">
                    <span className="font-medium dark:text-white">{user.department || '未设置'}</span>
                    <button
                      onClick={() => {
                        setDepartment(user.department || '')
                        setShowDepartmentModal(true)
                      }}
                      className="text-primary-600 hover:text-primary-700 dark:text-primary-400 text-sm"
                    >
                      [修改]
                    </button>
                  </div>
                </div>
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">级别</label>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 text-sm rounded ${getLevelBadgeColor(user.level)}`}>
                      L{user.level} {USER_LEVEL_LABELS[user.level]}
                    </span>
                    <button
                      onClick={() => setShowLevelModal(true)}
                      className="text-primary-600 hover:text-primary-700 dark:text-primary-400 text-sm"
                    >
                      [修改级别]
                    </button>
                  </div>
                </div>
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">账户状态</label>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleToggleStatus}
                      disabled={isUpdating}
                      className="flex items-center gap-2"
                    >
                      {user.is_active ? (
                        <ToggleRight className="h-6 w-6 text-green-500" />
                      ) : (
                        <ToggleLeft className="h-6 w-6 text-gray-400" />
                      )}
                      <span className="text-sm text-gray-600 dark:text-slate-400">
                        {user.is_active ? '点击禁用' : '点击启用'}
                      </span>
                    </button>
                  </div>
                </div>
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">超级用户</label>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleToggleSuperuser}
                      disabled={isUpdating}
                      className="flex items-center gap-2"
                    >
                      <Shield className={`h-5 w-5 ${user.is_superuser ? 'text-red-500' : 'text-gray-400'}`} />
                      <span className="text-sm text-gray-600 dark:text-slate-400">
                        {user.is_superuser ? '取消超管' : '设为超管'}
                      </span>
                    </button>
                  </div>
                </div>
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">创建时间</label>
                  <p className="font-medium dark:text-white">{formatDate(user.created_at)}</p>
                </div>
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">更新时间</label>
                  <p className="font-medium dark:text-white">{formatDate(user.updated_at)}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6 dark:bg-slate-800">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold dark:text-white">
                  知识库权限 ({permissions.length})
                </h2>
                <button
                  onClick={() => setShowPermissionModal(true)}
                  className="flex items-center gap-2 px-3 py-1.5 bg-primary-500 text-white rounded-lg hover:bg-primary-600 text-sm"
                >
                  <Plus className="h-4 w-4" />
                  授予权限
                </button>
              </div>

              {permissions.length === 0 ? (
                <p className="text-gray-500 text-center py-8 dark:text-slate-400">
                  该用户暂无知识库权限
                </p>
              ) : (
                <div className="space-y-2">
                  {permissions.map((perm) => (
                    <div
                      key={perm.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 dark:border-slate-600 dark:hover:bg-slate-700/50"
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/30">
                          <Database className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                          <div className="font-medium dark:text-white">{perm.kb_name}</div>
                          <div className="text-sm text-gray-500 dark:text-slate-400">
                            授予时间: {formatDate(perm.granted_at)}
                            {perm.expires_at && ` · 过期时间: ${formatDate(perm.expires_at)}`}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-1 text-xs rounded ${getRoleBadgeColor(perm.role)}`}>
                          {getRoleLabel(perm.role)}
                        </span>
                        <button
                          onClick={() => handleRevokePermission(perm)}
                          className="p-2 hover:bg-red-50 rounded text-red-500 dark:hover:bg-red-900/20 dark:text-red-400"
                          title="撤销权限"
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
        </div>
      </div>

      {showLevelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 dark:bg-slate-800">
            <h2 className="text-lg font-semibold mb-4 dark:text-white">修改用户级别</h2>
            
            <div className="mb-4">
              <p className="text-sm text-gray-500 dark:text-slate-400">
                当前用户：<span className="font-medium text-gray-900 dark:text-white">{user.name}</span>
              </p>
              <p className="text-sm text-gray-500 dark:text-slate-400">
                当前级别：<span className={`px-2 py-0.5 text-xs rounded ${getLevelBadgeColor(user.level)}`}>L{user.level}</span>
              </p>
            </div>

            <div className="space-y-2 mb-6">
              {[4, 3, 2, 1].map((level) => (
                <label
                  key={level}
                  className={`flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${
                    selectedLevel === level
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                      : 'border-gray-200 hover:bg-gray-50 dark:border-slate-600 dark:hover:bg-slate-700/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="level"
                    value={level}
                    checked={selectedLevel === level}
                    onChange={() => setSelectedLevel(level)}
                    className="mt-1"
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 text-xs rounded ${getLevelBadgeColor(level)}`}>
                        L{level}
                      </span>
                      <span className="font-medium dark:text-white">{USER_LEVEL_LABELS[level]}</span>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
                      {getLevelDescription(level)}
                    </p>
                  </div>
                </label>
              ))}
            </div>

            <div className="bg-yellow-50 dark:bg-yellow-900/20 p-3 rounded-lg mb-4">
              <p className="text-sm text-yellow-700 dark:text-yellow-400">
                ⚠️ 注意：降低级别不会自动撤销已有的高级权限
              </p>
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowLevelModal(false)
                  setSelectedLevel(user.level)
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 dark:bg-slate-600 dark:text-slate-300 dark:hover:bg-slate-500"
              >
                取消
              </button>
              <button
                onClick={handleUpdateLevel}
                disabled={isUpdating || selectedLevel === user.level}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50"
              >
                {isUpdating ? '修改中...' : '确认修改'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showPermissionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 dark:bg-slate-800">
            <h2 className="text-lg font-semibold mb-4 dark:text-white">授予知识库权限</h2>
            
            <div className="mb-4">
              <p className="text-sm text-gray-500 dark:text-slate-400">
                用户：<span className="font-medium text-gray-900 dark:text-white">{user.name}</span>
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                  选择知识库
                </label>
                <select
                  value={newPermission.kb_id}
                  onChange={(e) => setNewPermission({ ...newPermission, kb_id: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                >
                  <option value="">请选择知识库</option>
                  {availableKnowledgeBases.map((kb) => (
                    <option key={kb.id} value={kb.id}>
                      {kb.name}
                    </option>
                  ))}
                </select>
                {availableKnowledgeBases.length === 0 && (
                  <p className="text-sm text-gray-500 mt-1">该用户已拥有所有知识库的权限</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                  授予角色
                </label>
                <div className="space-y-2">
                  {['viewer', 'editor', 'admin', 'owner'].map((role) => (
                    <label
                      key={role}
                      className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${
                        newPermission.role === role
                          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                          : 'border-gray-200 hover:bg-gray-50 dark:border-slate-600 dark:hover:bg-slate-700/50'
                      }`}
                    >
                      <input
                        type="radio"
                        name="role"
                        value={role}
                        checked={newPermission.role === role}
                        onChange={() => setNewPermission({ ...newPermission, role })}
                        className="mt-0.5"
                      />
                      <div>
                        <span className={`px-2 py-0.5 text-xs rounded ${getRoleBadgeColor(role)}`}>
                          {getRoleLabel(role)}
                        </span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => {
                  setShowPermissionModal(false)
                  setNewPermission({ kb_id: '', role: 'viewer' })
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 dark:bg-slate-600 dark:text-slate-300 dark:hover:bg-slate-500"
              >
                取消
              </button>
              <button
                onClick={handleGrantPermission}
                disabled={isUpdating || !newPermission.kb_id}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50"
              >
                {isUpdating ? '授权中...' : '确认授权'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showDepartmentModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 dark:bg-slate-800">
            <h2 className="text-lg font-semibold mb-4 dark:text-white">修改部门</h2>
            
            <div className="mb-4">
              <p className="text-sm text-gray-500 dark:text-slate-400">
                用户：<span className="font-medium text-gray-900 dark:text-white">{user.name}</span>
              </p>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                部门名称
              </label>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                placeholder="请输入部门名称"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
              />
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
                留空表示不设置部门
              </p>
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowDepartmentModal(false)
                  setDepartment(user.department || '')
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 dark:bg-slate-600 dark:text-slate-300 dark:hover:bg-slate-500"
              >
                取消
              </button>
              <button
                onClick={handleUpdateDepartment}
                disabled={isUpdating}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50"
              >
                {isUpdating ? '修改中...' : '确认修改'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
