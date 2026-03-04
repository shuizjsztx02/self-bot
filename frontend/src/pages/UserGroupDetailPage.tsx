import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Users, UserPlus, UserMinus, MessageSquare } from 'lucide-react'
import { knowledgeApi } from '../services/knowledgeApi'
import { getErrorMessage } from '../utils/errorHandler'
import Sidebar from '../components/Sidebar'
import UserSelector from '../components/UserSelector'
import type { User } from '../types/knowledge'

interface GroupMember {
  id: string
  user_id: string
  user_name: string
  user_email: string
  is_manager: boolean
  joined_at: string
}

interface UserGroupDetail {
  id: string
  name: string
  description: string | null
  parent_id: string | null
  member_count: number
  members: GroupMember[]
  created_at: string
}

export default function UserGroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const navigate = useNavigate()
  
  const [group, setGroup] = useState<UserGroupDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [newMemberIsManager, setNewMemberIsManager] = useState(false)

  useEffect(() => {
    if (groupId) {
      fetchGroupDetail()
    }
  }, [groupId])

  const fetchGroupDetail = async () => {
    if (!groupId) return
    
    setIsLoading(true)
    setError(null)
    try {
      const data = await knowledgeApi.getUserGroup(groupId)
      setGroup(data)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleAddMember = async () => {
    if (!selectedUser) {
      setError('请选择要添加的用户')
      return
    }

    if (!groupId) return

    setIsLoading(true)
    setError(null)
    try {
      await knowledgeApi.addGroupMember(groupId, {
        user_id: selectedUser.id,
        is_manager: newMemberIsManager,
      })
      setSelectedUser(null)
      setNewMemberIsManager(false)
      fetchGroupDetail()
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleRemoveMember = async (userId: string, userName: string) => {
    if (!groupId) return
    if (!confirm(`确定要移除成员 "${userName}" 吗？`)) return

    setIsLoading(true)
    setError(null)
    try {
      await knowledgeApi.removeGroupMember(groupId, userId)
      fetchGroupDetail()
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleToggleManager = async (userId: string, currentStatus: boolean, userName: string) => {
    if (!groupId) return
    if (!confirm(`${currentStatus ? '取消' : '设置'} "${userName}" 的管理员权限？`)) return

    setIsLoading(true)
    setError(null)
    try {
      await knowledgeApi.removeGroupMember(groupId, userId)
      await knowledgeApi.addGroupMember(groupId, {
        user_id: userId,
        is_manager: !currentStatus,
      })
      fetchGroupDetail()
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
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

  if (isLoading && !group) {
    return (
      <div className="flex h-screen bg-slate-100 dark:bg-slate-900">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    )
  }

  if (!group) {
    return (
      <div className="flex h-screen bg-slate-100 dark:bg-slate-900">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-gray-500 dark:text-slate-400">用户组不存在</div>
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
              onClick={() => navigate('/user-groups')}
              className="flex items-center gap-2 text-gray-600 hover:text-primary-600 transition-colors dark:text-slate-400 dark:hover:text-primary-400"
            >
              <ArrowLeft className="h-5 w-5" />
              <span className="text-sm font-medium">返回用户组列表</span>
            </button>
            <div className="h-6 w-px bg-gray-200 dark:bg-slate-600" />
            <div className="flex items-center gap-2">
              <Users className="h-6 w-6 text-blue-500" />
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{group.name}</h1>
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
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">用户组名称</label>
                  <p className="font-medium dark:text-white">{group.name}</p>
                </div>
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">成员数量</label>
                  <p className="font-medium dark:text-white">{group.member_count} 人</p>
                </div>
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">描述</label>
                  <p className="font-medium dark:text-white">{group.description || '暂无描述'}</p>
                </div>
                <div>
                  <label className="text-sm text-gray-500 dark:text-slate-400">创建时间</label>
                  <p className="font-medium dark:text-white">{formatDate(group.created_at)}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6 dark:bg-slate-800">
              <h2 className="text-lg font-semibold mb-4 dark:text-white">添加成员</h2>
              <div className="space-y-3">
                <UserSelector
                  selectedUserId={selectedUser?.id || null}
                  onSelect={(user) => setSelectedUser(user)}
                  excludeIds={group.members.map((m) => m.user_id)}
                  placeholder="搜索用户姓名、邮箱或部门..."
                />
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={newMemberIsManager}
                      onChange={(e) => setNewMemberIsManager(e.target.checked)}
                      className="rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-600 dark:text-slate-400">设为组管理员</span>
                  </label>
                  <button
                    onClick={handleAddMember}
                    disabled={isLoading || !selectedUser}
                    className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 flex items-center gap-2"
                  >
                    <UserPlus className="h-4 w-4" />
                    添加成员
                  </button>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6 dark:bg-slate-800">
              <h2 className="text-lg font-semibold mb-4 dark:text-white">
                成员列表 ({group.members.length})
              </h2>
              
              {group.members.length === 0 ? (
                <p className="text-gray-500 text-center py-8 dark:text-slate-400">暂无成员</p>
              ) : (
                <div className="space-y-2">
                  {group.members.map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 dark:border-slate-600 dark:hover:bg-slate-700/50"
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/30">
                          <span className="text-primary-600 font-medium dark:text-primary-400">
                            {member.user_name.charAt(0).toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium dark:text-white">{member.user_name}</span>
                            {member.is_manager && (
                              <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded dark:bg-blue-900/50 dark:text-blue-300">
                                管理员
                              </span>
                            )}
                          </div>
                          <div className="text-sm text-gray-500 dark:text-slate-400">{member.user_email}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleToggleManager(member.user_id, member.is_manager, member.user_name)}
                          className={`px-3 py-1 text-sm rounded ${
                            member.is_manager
                              ? 'text-orange-600 hover:bg-orange-50 dark:text-orange-400 dark:hover:bg-orange-900/20'
                              : 'text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-900/20'
                          }`}
                        >
                          {member.is_manager ? '取消管理员' : '设为管理员'}
                        </button>
                        <button
                          onClick={() => handleRemoveMember(member.user_id, member.user_name)}
                          className="p-2 hover:bg-red-50 rounded text-red-500 dark:hover:bg-red-900/20 dark:text-red-400"
                          title="移除成员"
                        >
                          <UserMinus className="h-4 w-4" />
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
    </div>
  )
}
