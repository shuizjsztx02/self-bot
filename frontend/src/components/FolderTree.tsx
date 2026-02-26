import { useState } from 'react'
import { Folder, FolderOpen, ChevronRight, ChevronDown, Plus, MoreHorizontal, Trash2, Edit2 } from 'lucide-react'
import type { Folder as FolderType, FolderCreate } from '../types/knowledge'

interface FolderTreeProps {
  folders: FolderType[]
  currentFolderId?: string | null
  onSelectFolder: (folder: FolderType | null) => void
  onCreateFolder: (data: FolderCreate) => Promise<void>
  onRenameFolder: (folderId: string, name: string) => Promise<void>
  onDeleteFolder: (folderId: string) => Promise<void>
  isLoading?: boolean
}

interface FolderNode {
  folder: FolderType
  children: FolderNode[]
}

export default function FolderTree({
  folders,
  currentFolderId,
  onSelectFolder,
  onCreateFolder,
  onRenameFolder,
  onDeleteFolder,
  isLoading = false,
}: FolderTreeProps) {
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [showNewFolderInput, setShowNewFolderInput] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [contextMenu, setContextMenu] = useState<{ folderId: string; x: number; y: number } | null>(null)
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')

  const buildTree = (folders: FolderType[]): FolderNode[] => {
    const folderMap = new Map<string, FolderNode>()
    const rootNodes: FolderNode[] = []

    folders.forEach((folder) => {
      folderMap.set(folder.id, { folder, children: [] })
    })

    folders.forEach((folder) => {
      const node = folderMap.get(folder.id)!
      if (folder.parent_id && folderMap.has(folder.parent_id)) {
        folderMap.get(folder.parent_id)!.children.push(node)
      } else {
        rootNodes.push(node)
      }
    })

    return rootNodes
  }

  const toggleExpand = (folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(folderId)) {
        next.delete(folderId)
      } else {
        next.add(folderId)
      }
      return next
    })
  }

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return

    await onCreateFolder({
      name: newFolderName.trim(),
      parent_id: currentFolderId || undefined,
    })

    setNewFolderName('')
    setShowNewFolderInput(false)
  }

  const handleContextMenu = (e: React.MouseEvent, folderId: string) => {
    e.preventDefault()
    setContextMenu({ folderId, x: e.clientX, y: e.clientY })
  }

  const handleDeleteFolder = async (folderId: string) => {
    setContextMenu(null)
    await onDeleteFolder(folderId)
  }

  const handleStartEdit = (folder: FolderType) => {
    setContextMenu(null)
    setEditingFolderId(folder.id)
    setEditingName(folder.name)
  }

  const handleRenameFolder = async () => {
    if (!editingFolderId || !editingName.trim()) return

    await onRenameFolder(editingFolderId, editingName.trim())
    setEditingFolderId(null)
    setEditingName('')
  }

  const renderFolderNode = (node: FolderNode, depth: number = 0) => {
    const { folder, children } = node
    const isExpanded = expandedFolders.has(folder.id)
    const isSelected = currentFolderId === folder.id
    const hasChildren = children.length > 0
    const isEditing = editingFolderId === folder.id

    return (
      <div key={folder.id}>
        <div
          className={`flex items-center gap-1 py-1.5 px-2 rounded cursor-pointer group ${
            isSelected ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-100'
          }`}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
          onClick={() => onSelectFolder(folder)}
          onContextMenu={(e) => handleContextMenu(e, folder.id)}
        >
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                toggleExpand(folder.id)
              }}
              className="p-0.5 hover:bg-gray-200 rounded"
            >
              {isExpanded ? (
                <ChevronDown className="h-3 w-3 text-gray-400" />
              ) : (
                <ChevronRight className="h-3 w-3 text-gray-400" />
              )}
            </button>
          ) : (
            <span className="w-4" />
          )}

          {isSelected ? (
            <FolderOpen className="h-4 w-4 text-blue-500 flex-shrink-0" />
          ) : (
            <Folder className="h-4 w-4 text-gray-400 flex-shrink-0" />
          )}

          {isEditing ? (
            <input
              type="text"
              value={editingName}
              onChange={(e) => setEditingName(e.target.value)}
              onBlur={handleRenameFolder}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRenameFolder()
                if (e.key === 'Escape') setEditingFolderId(null)
              }}
              className="flex-1 text-sm px-1 py-0.5 border rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span className="text-sm truncate">{folder.name}</span>
          )}

          <button
            onClick={(e) => {
              e.stopPropagation()
              handleContextMenu(e, folder.id)
            }}
            className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-gray-200 rounded"
          >
            <MoreHorizontal className="h-3 w-3 text-gray-400" />
          </button>
        </div>

        {isExpanded && hasChildren && (
          <div>
            {children.map((child) => renderFolderNode(child, depth + 1))}
          </div>
        )}
      </div>
    )
  }

  const tree = buildTree(folders)

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">文件夹</span>
        <button
          onClick={() => setShowNewFolderInput(true)}
          disabled={isLoading}
          className="p-1 hover:bg-gray-100 rounded text-gray-500 hover:text-gray-700"
          title="新建文件夹"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {showNewFolderInput && (
        <div className="flex items-center gap-1 mb-2 px-2">
          <Folder className="h-4 w-4 text-gray-400 flex-shrink-0" />
          <input
            type="text"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleCreateFolder()
              if (e.key === 'Escape') {
                setShowNewFolderInput(false)
                setNewFolderName('')
              }
            }}
            onBlur={() => {
              if (!newFolderName.trim()) {
                setShowNewFolderInput(false)
              }
            }}
            placeholder="文件夹名称"
            className="flex-1 text-sm px-1 py-0.5 border rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            autoFocus
          />
        </div>
      )}

      <div
        className={`flex items-center gap-1 py-1.5 px-2 rounded cursor-pointer ${
          !currentFolderId ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-100'
        }`}
        onClick={() => onSelectFolder(null)}
      >
        <span className="w-4" />
        <Folder className={`h-4 w-4 ${!currentFolderId ? 'text-blue-500' : 'text-gray-400'}`} />
        <span className="text-sm">全部文件</span>
      </div>

      {tree.map((node) => renderFolderNode(node))}

      {folders.length === 0 && !showNewFolderInput && (
        <div className="text-sm text-gray-400 text-center py-2">
          暂无文件夹
        </div>
      )}

      {contextMenu && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setContextMenu(null)}
          />
          <div
            className="fixed z-50 bg-white border rounded-lg shadow-lg py-1 min-w-[120px]"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <button
              onClick={() => {
                const folder = folders.find((f) => f.id === contextMenu.folderId)
                if (folder) handleStartEdit(folder)
              }}
              className="w-full px-3 py-1.5 text-left text-sm hover:bg-gray-100 flex items-center gap-2"
            >
              <Edit2 className="h-3 w-3" />
              重命名
            </button>
            <button
              onClick={() => handleDeleteFolder(contextMenu.folderId)}
              className="w-full px-3 py-1.5 text-left text-sm hover:bg-gray-100 text-red-600 flex items-center gap-2"
            >
              <Trash2 className="h-3 w-3" />
              删除
            </button>
          </div>
        </>
      )}
    </div>
  )
}
