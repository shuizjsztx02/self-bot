import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Users, MessageSquare, Search, UserPlus } from 'lucide-react'
import { knowledgeApi } from '../services/knowledgeApi'
import { getErrorMessage } from '../utils/errorHandler'
import Sidebar from '../components/Sidebar'
import { toast } from '../components/Toast'
import type { UserListItem, UserCreate } from '../types/knowledge'
import { USER_LEVEL_LABELS } from '../types/knowledge'

export default function UsersPage() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<UserListItem[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [newUser, setNewUser] = useState<UserCreate>({
    name: '',
    email: '',
    password: '',
    department: '',
    level: 1,
    is_superuser: false,
  })

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await knowledgeApi.listUsers({ search: searchTerm || undefined })
      setUsers(data.items)
      setTotal(data.total)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = () => {
    fetchUsers()
  }

  const handleCreateUser = async () => {
    if (!newUser.name.trim() || !newUser.email.trim() || !newUser.password.trim()) {
      toast.error('验证失败', '请填写必填字段')
      return
    }

    setIsCreating(true)
    try {
      await knowledgeApi.createUser({
        name: newUser.name.trim(),
        email: newUser.email.trim(),
        password: newUser.password,
        department: newUser.department?.trim() || undefined,
        level: newUser.level,
        is_superuser: newUser.is_superuser,
      })
      toast.success('创建成功', `用户 "${newUser.name}" 已创建`)
      setShowCreateModal(false)
      setNewUser({
        name: '',
        email: '',
        password: '',
        department: '',
        level: 1,
        is_superuser: false,
      })
      fetchUsers()
    } catch (e) {
      toast.error('创建失败', getErrorMessage(e))
    } finally {
      setIsCreating(false)
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('zh-CN')
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

  return (
    <div className="flex h-screen bg-slate-100 dark:bg-slate-900">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="border-b bg-white px-6 py-4 dark:bg-slate-800 dark:border-slate-700">
          <div className="flex items-center justify-between">
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
              <div className="flex items-center gap-2">
                <Users className="h-6 w-6 text-blue-500" />
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">用户管理</h1>
              </div>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600"
            >
              <Plus className="h-4 w-4" />
              创建用户
            </button>
          </div>
        </div>

        <div className="p-6">
          <div className="mb-6 flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="搜索用户姓名、邮箱或部门..."
                className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
              />
            </div>
            <button
              onClick={handleSearch}
              className="px-6 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600"
            >
              搜索
            </button>
          </div>

          {error && (
            <div className="mb-4 p-4 bg-red-50 text-red-600 rounded-lg dark:bg-red-900/30 dark:text-red-400">
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="flex items-center justify-center h-40">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-12 text-gray-500 dark:text-slate-400">
              暂无用户数据
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow dark:bg-slate-800 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-slate-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-slate-400">
                      用户
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-slate-400">
                      部门
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-slate-400">
                      级别
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-slate-400">
                      状态
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-slate-400">
                      创建时间
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-slate-400">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                  {users.map((user) => (
                    <tr
                      key={user.id}
                      className="hover:bg-gray-50 dark:hover:bg-slate-700/50 cursor-pointer"
                      onClick={() => navigate(`/users/${user.id}`)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/30">
                            <span className="text-primary-600 font-medium dark:text-primary-400">
                              {user.name.charAt(0).toUpperCase()}
                            </span>
                          </div>
                          <div className="ml-4">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-gray-900 dark:text-white">{user.name}</span>
                              {user.is_superuser && (
                                <span className="px-2 py-0.5 text-xs rounded bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300">
                                  超管
                                </span>
                              )}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-slate-400">{user.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-gray-500 dark:text-slate-400">
                        {user.department || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs rounded ${getLevelBadgeColor(user.level)}`}>
                          L{user.level} {USER_LEVEL_LABELS[user.level]}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {user.is_active ? (
                          <span className="px-2 py-1 text-xs rounded bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300">
                            已激活
                          </span>
                        ) : (
                          <span className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                            已禁用
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-gray-500 dark:text-slate-400">
                        {formatDate(user.created_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            navigate(`/users/${user.id}`)
                          }}
                          className="text-primary-600 hover:text-primary-900 dark:text-primary-400 dark:hover:text-primary-300"
                        >
                          查看详情
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              <div className="px-6 py-4 border-t dark:border-slate-700 text-sm text-gray-500 dark:text-slate-400">
                共 {total} 个用户
              </div>
            </div>
          )}
        </div>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 dark:bg-slate-800">
            <h2 className="text-lg font-semibold mb-4 dark:text-white">创建用户</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                  姓名 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newUser.name}
                  onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                  placeholder="请输入姓名"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                  邮箱 <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                  placeholder="请输入邮箱"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                  密码 <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  value={newUser.password}
                  onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                  placeholder="请输入密码（至少6位）"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                  部门
                </label>
                <input
                  type="text"
                  value={newUser.department || ''}
                  onChange={(e) => setNewUser({ ...newUser, department: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                  placeholder="请输入部门（可选）"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                  级别
                </label>
                <select
                  value={newUser.level}
                  onChange={(e) => setNewUser({ ...newUser, level: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                >
                  <option value={1}>L1 - 查看者</option>
                  <option value={2}>L2 - 编辑者</option>
                  <option value={3}>L3 - 管理员</option>
                  <option value={4}>L4 - 所有者</option>
                </select>
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_superuser"
                  checked={newUser.is_superuser}
                  onChange={(e) => setNewUser({ ...newUser, is_superuser: e.target.checked })}
                  className="rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                />
                <label htmlFor="is_superuser" className="text-sm text-gray-700 dark:text-slate-300">
                  设为超级用户
                </label>
              </div>
            </div>
            
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setNewUser({
                    name: '',
                    email: '',
                    password: '',
                    department: '',
                    level: 1,
                    is_superuser: false,
                  })
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 dark:bg-slate-600 dark:text-slate-300 dark:hover:bg-slate-500"
              >
                取消
              </button>
              <button
                onClick={handleCreateUser}
                disabled={isCreating}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2"
              >
                {isCreating ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                    创建中...
                  </>
                ) : (
                  <>
                    <UserPlus className="h-4 w-4" />
                    创建用户
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
