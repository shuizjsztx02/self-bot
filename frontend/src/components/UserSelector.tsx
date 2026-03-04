import { useState, useEffect, useRef } from 'react'
import { Search, X, Check } from 'lucide-react'
import { knowledgeApi } from '../services/knowledgeApi'
import type { User } from '../types/knowledge'

interface UserSelectorProps {
  selectedUserId: string | null
  onSelect: (user: User) => void
  excludeIds?: string[]
  placeholder?: string
}

export function UserSelector({ selectedUserId, onSelect, excludeIds = [], placeholder = '搜索用户...' }: UserSelectorProps) {
  const [users, setUsers] = useState<User[]>([])
  const [filteredUsers, setFilteredUsers] = useState<User[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchUsers()
  }, [])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (searchTerm) {
      const filtered = users.filter(
        (user) =>
          !excludeIds.includes(user.id) &&
          (user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (user.department && user.department.toLowerCase().includes(searchTerm.toLowerCase())))
      )
      setFilteredUsers(filtered)
    } else {
      setFilteredUsers(users.filter((user) => !excludeIds.includes(user.id)))
    }
  }, [searchTerm, users, excludeIds])

  const fetchUsers = async () => {
    setIsLoading(true)
    try {
      const data = await knowledgeApi.listAllUsers()
      setUsers(data)
      setFilteredUsers(data.filter((user) => !excludeIds.includes(user.id)))
    } catch (error) {
      console.error('Failed to fetch users:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelect = (user: User) => {
    onSelect(user)
    setSearchTerm('')
    setIsOpen(false)
  }

  const selectedUser = users.find((u) => u.id === selectedUserId)

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
    <div ref={dropdownRef} className="relative">
      <div
        className="flex items-center gap-2 w-full px-3 py-2 border rounded-lg cursor-pointer bg-white dark:bg-slate-700 dark:border-slate-600 hover:border-primary-500 focus-within:border-primary-500"
        onClick={() => {
          setIsOpen(true)
          inputRef.current?.focus()
        }}
      >
        {selectedUser && !isOpen ? (
          <>
            <div className="flex-1 flex items-center gap-2">
              <span className="font-medium dark:text-white">{selectedUser.name}</span>
              <span className="text-sm text-gray-500 dark:text-slate-400">{selectedUser.email}</span>
              <span className={`px-1.5 py-0.5 text-xs rounded ${getLevelBadgeColor(selectedUser.level)}`}>
                L{selectedUser.level}
              </span>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onSelect(null as any)
              }}
              className="p-1 hover:bg-gray-100 rounded dark:hover:bg-slate-600"
            >
              <X className="h-4 w-4 text-gray-400" />
            </button>
          </>
        ) : (
          <>
            <Search className="h-4 w-4 text-gray-400 flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onFocus={() => setIsOpen(true)}
              placeholder={placeholder}
              className="flex-1 outline-none bg-transparent dark:text-white placeholder-gray-400"
            />
          </>
        )}
      </div>

      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto dark:bg-slate-700 dark:border-slate-600">
          {isLoading ? (
            <div className="flex items-center justify-center py-4">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-500"></div>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-500 dark:text-slate-400 text-center">
              {searchTerm ? '未找到匹配的用户' : '暂无可选用户'}
            </div>
          ) : (
            filteredUsers.map((user) => (
              <div
                key={user.id}
                onClick={() => handleSelect(user)}
                className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-600"
              >
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <span className="font-medium dark:text-white">{user.name}</span>
                      <span className={`px-1.5 py-0.5 text-xs rounded ${getLevelBadgeColor(user.level)}`}>
                        L{user.level}
                      </span>
                      {user.is_superuser && (
                        <span className="px-1.5 py-0.5 text-xs rounded bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300">
                          超管
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-slate-400">
                      <span>{user.email}</span>
                      {user.department && <span>· {user.department}</span>}
                    </div>
                  </div>
                </div>
                {selectedUserId === user.id && (
                  <Check className="h-4 w-4 text-primary-500" />
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default UserSelector
