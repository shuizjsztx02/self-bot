import { useState, useEffect } from 'react'
import { Plus, Users, Edit, Trash2, UserPlus, UserMinus } from 'lucide-react'
import knowledgeApi from '../services/knowledgeApi'
import { getErrorMessage } from '../utils/errorHandler'

interface UserGroup {
  id: string
  name: string
  description: string | null
  parent_id: string | null
  member_count: number
  created_at: string
}

interface GroupMember {
  id: string
  user_id: string
  user_name: string
  user_email: string
  is_manager: boolean
  joined_at: string
}

export default function UserGroupsPage() {
  const [groups, setGroups] = useState<UserGroup[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [selectedGroup, setSelectedGroup] = useState<UserGroup | null>(null)
  const [members, setMembers] = useState<GroupMember[]>([])
  const [newGroupName, setNewGroupName] = useState('')
  const [newGroupDesc, setNewGroupDesc] = useState('')
  const [newMemberId, setNewMemberId] = useState('')
  const [newMemberIsManager, setNewMemberIsManager] = useState(false)

  useEffect(() => {
    fetchGroups()
  }, [])

  const fetchGroups = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await knowledgeApi.listUserGroups()
      setGroups(data)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) {
      setError('请输入用户组名称')
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      await knowledgeApi.createUserGroup({
        name: newGroupName.trim(),
        description: newGroupDesc.trim() || undefined,
      })
      setShowCreateModal(false)
      setNewGroupName('')
      setNewGroupDesc('')
      fetchGroups()
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteGroup = async (groupId: string) => {
    if (!confirm('确定要删除此用户组吗？')) return

    setIsLoading(true)
    setError(null)
    try {
      await knowledgeApi.deleteUserGroup(groupId)
      setGroups(groups.filter(g => g.id !== groupId))
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleViewGroup = async (group: UserGroup) => {
    setSelectedGroup(group)
    setShowDetailModal(true)
    setMembers([])
    
    try {
      const data = await knowledgeApi.getUserGroup(group.id)
      setMembers(data.members || [])
    } catch (e) {
      setError(getErrorMessage(e))
    }
  }

  const handleAddMember = async () => {
    if (!newMemberId.trim()) {
      setError('请输入用户ID')
      return
    }

    if (!selectedGroup) return

    setIsLoading(true)
    setError(null)
    try {
      await knowledgeApi.addGroupMember(selectedGroup.id, {
        user_id: newMemberId.trim(),
        is_manager: newMemberIsManager,
      })
      setNewMemberId('')
      setNewMemberIsManager(false)
      handleViewGroup(selectedGroup)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const handleRemoveMember = async (userId: string) => {
    if (!selectedGroup) return
    if (!confirm('确定要移除此成员吗？')) return

    setIsLoading(true)
    setError(null)
    try {
      await knowledgeApi.removeGroupMember(selectedGroup.id, userId)
      handleViewGroup(selectedGroup)
    } catch (e) {
      setError(getErrorMessage(e))
    } finally {
      setIsLoading(false)
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('zh-CN')
  }

  return (
    <div className="h-full flex flex-col">
      <div className="border-b bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">用户组管理</h1>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            <Plus className="h-4 w-4" />
            创建用户组
          </button>
        </div>
      </div>

      <div className="flex-1 p-6 overflow-y-auto">
        {error && (
          <div className="mb-4 p-4 bg-red-50 text-red-600 rounded-lg">
            {error}
          </div>
        )}

        {isLoading && groups.length === 0 ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : groups.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            暂无用户组，点击"创建用户组"添加
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {groups.map((group) => (
              <div
                key={group.id}
                className="border rounded-lg p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Users className="h-5 w-5 text-blue-500" />
                    <h3 className="font-semibold">{group.name}</h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleViewGroup(group)}
                      className="p-1 hover:bg-gray-100 rounded"
                      title="查看详情"
                    >
                      <Edit className="h-4 w-4 text-gray-500" />
                    </button>
                    <button
                      onClick={() => handleDeleteGroup(group.id)}
                      className="p-1 hover:bg-red-50 rounded"
                      title="删除"
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </button>
                  </div>
                </div>
                
                {group.description && (
                  <p className="text-sm text-gray-600 mb-3">{group.description}</p>
                )}
                
                <div className="flex items-center justify-between text-sm text-gray-500">
                  <span>{group.member_count} 成员</span>
                  <span>创建于 {formatDate(group.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Group Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">创建用户组</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  组名称 *
                </label>
                <input
                  type="text"
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  placeholder="输入用户组名称"
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  描述
                </label>
                <textarea
                  value={newGroupDesc}
                  onChange={(e) => setNewGroupDesc(e.target.value)}
                  placeholder="输入描述（可选）"
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                />
              </div>
            </div>
            
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setNewGroupName('')
                  setNewGroupDesc('')
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                取消
              </button>
              <button
                onClick={handleCreateGroup}
                disabled={isLoading}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Group Detail Modal */}
      {showDetailModal && selectedGroup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
              <div className="p-4 border-b">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">{selectedGroup.name} - 成员管理</h2>
                  <button
                    onClick={() => {
                      setShowDetailModal(false)
                      setSelectedGroup(null)
                      setMembers([])
                    }}
                    className="text-gray-500 hover:text-gray-700 text-2xl"
                  >
                    ×
                  </button>
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto p-4">
                <div className="mb-4">
                  <h3 className="font-medium mb-2">添加成员</h3>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newMemberId}
                      onChange={(e) => setNewMemberId(e.target.value)}
                      placeholder="用户ID"
                      className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={newMemberIsManager}
                        onChange={(e) => setNewMemberIsManager(e.target.checked)}
                        className="rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                      />
                      <span className="text-sm">管理员</span>
                    </label>
                    <button
                      onClick={handleAddMember}
                      disabled={isLoading}
                      className="px-3 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
                    >
                      <UserPlus className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                
                <div>
                  <h3 className="font-medium mb-2">成员列表 ({members.length})</h3>
                  {members.length === 0 ? (
                    <p className="text-gray-500 text-center py-4">暂无成员</p>
                  ) : (
                    <div className="space-y-2">
                      {members.map((member) => (
                        <div
                          key={member.id}
                          className="flex items-center justify-between p-3 border rounded-lg"
                        >
                          <div>
                            <div className="font-medium">{member.user_name}</div>
                            <div className="text-sm text-gray-500">{member.user_email}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            {member.is_manager && (
                              <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">
                                管理员
                              </span>
                            )}
                            <button
                              onClick={() => handleRemoveMember(member.user_id)}
                              className="p-1 hover:bg-red-50 rounded"
                              title="移除"
                            >
                              <UserMinus className="h-4 w-4 text-red-500" />
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
      )}
    </div>
  )
}
