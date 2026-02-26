import api from './api'
import type {
  KnowledgeBase,
  KnowledgeBaseCreate,
  KnowledgeBaseUpdate,
  KnowledgeBaseStats,
  Document,
  DocumentChunk,
  DocumentVersion,
  SearchRequest,
  SearchResponse,
  Folder,
  FolderCreate,
  KBPermission,
  User,
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  HybridSearchRequest,
  AttributionSearchRequest,
  RAGResponse,
  CompressionSearchRequest,
  CompressionSearchResponse,
  UserGroup,
  UserGroupDetail,
} from '../types/knowledge'
import { throwApiError } from '../utils/errorHandler'

export const knowledgeApi = {
  // ==================== 知识库管理 ====================

  createKnowledgeBase: async (data: KnowledgeBaseCreate): Promise<KnowledgeBase> => {
    try {
      const response = await api.post<KnowledgeBase>('/knowledge-bases', data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  listKnowledgeBases: async (params?: {
    skip?: number
    limit?: number
    owner_id?: string
  }): Promise<KnowledgeBase[]> => {
    try {
      const response = await api.get<KnowledgeBase[]>('/knowledge-bases', { params })
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  getKnowledgeBase: async (id: string): Promise<KnowledgeBase> => {
    try {
      const response = await api.get<KnowledgeBase>(`/knowledge-bases/${id}`)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  updateKnowledgeBase: async (id: string, data: KnowledgeBaseUpdate): Promise<KnowledgeBase> => {
    try {
      const response = await api.put<KnowledgeBase>(`/knowledge-bases/${id}`, data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  deleteKnowledgeBase: async (id: string): Promise<void> => {
    try {
      await api.delete(`/knowledge-bases/${id}`)
    } catch (error) {
      throwApiError(error)
    }
  },

  getKnowledgeBaseStats: async (id: string): Promise<KnowledgeBaseStats> => {
    try {
      const response = await api.get<KnowledgeBaseStats>(`/knowledge-bases/${id}/stats`)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  // ==================== 文档管理 ====================

  uploadDocument: async (
    kbId: string,
    file: File,
    metadata?: {
      folder_id?: string
      title?: string
      author?: string
      source?: string
      tags?: string[]
    },
    onProgress?: (progress: number) => void
  ): Promise<Document> => {
    try {
      const formData = new FormData()
      formData.append('kb_id', kbId)
      formData.append('file', file)
      if (metadata?.folder_id) formData.append('folder_id', metadata.folder_id)
      if (metadata?.title) formData.append('title', metadata.title)
      if (metadata?.author) formData.append('author', metadata.author)
      if (metadata?.source) formData.append('source', metadata.source)
      if (metadata?.tags) formData.append('tags', metadata.tags.join(','))

      const response = await api.post<Document>('/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (e) => {
          if (e.total && onProgress) {
            onProgress(Math.round((e.loaded / e.total) * 100))
          }
        },
      })
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  listDocuments: async (kbId: string, params?: {
    folder_id?: string
    status?: string
    skip?: number
    limit?: number
  }): Promise<Document[]> => {
    try {
      const response = await api.get<Document[]>('/documents', {
        params: { kb_id: kbId, ...params },
      })
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  getDocument: async (docId: string): Promise<Document> => {
    try {
      const response = await api.get<Document>(`/documents/${docId}`)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  deleteDocument: async (docId: string): Promise<void> => {
    try {
      await api.delete(`/documents/${docId}`)
    } catch (error) {
      throwApiError(error)
    }
  },

  updateDocument: async (docId: string, data: {
    title?: string
    author?: string
    source?: string
    tags?: string[]
    folder_id?: string
  }): Promise<Document> => {
    try {
      const response = await api.put<Document>(`/documents/${docId}`, data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  reprocessDocument: async (docId: string): Promise<{ message: string; document_id: string }> => {
    try {
      const response = await api.post<{ message: string; document_id: string }>(`/documents/${docId}/reprocess`)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  getDocumentChunks: async (docId: string): Promise<DocumentChunk[]> => {
    try {
      const response = await api.get<DocumentChunk[]>(`/documents/${docId}/chunks`)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  getDocumentVersions: async (docId: string): Promise<DocumentVersion[]> => {
    try {
      const response = await api.get<DocumentVersion[]>(`/documents/${docId}/versions`)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  // ==================== 搜索 ====================

  search: async (request: SearchRequest): Promise<SearchResponse> => {
    try {
      const response = await api.post<SearchResponse>('/search', request)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  searchKnowledgeBase: async (kbId: string, request: SearchRequest): Promise<SearchResponse> => {
    try {
      const response = await api.post<SearchResponse>(`/search/kb/${kbId}`, request)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  hybridSearch: async (request: HybridSearchRequest): Promise<SearchResponse> => {
    try {
      const response = await api.post<SearchResponse>('/search/hybrid', request)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  searchWithAttribution: async (request: AttributionSearchRequest): Promise<RAGResponse> => {
    try {
      const response = await api.post<RAGResponse>('/search/with-attribution', request)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  searchWithCompression: async (request: CompressionSearchRequest): Promise<CompressionSearchResponse> => {
    try {
      const response = await api.post<CompressionSearchResponse>('/search/with-compression', request)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  // ==================== 文件夹管理 ====================

  createFolder: async (kbId: string, data: FolderCreate): Promise<Folder> => {
    try {
      const response = await api.post<Folder>(`/knowledge-bases/${kbId}/folders`, data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  listFolders: async (kbId: string, parentId?: string): Promise<Folder[]> => {
    try {
      const response = await api.get<Folder[]>(`/knowledge-bases/${kbId}/folders`, {
        params: { parent_id: parentId },
      })
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  deleteFolder: async (kbId: string, folderId: string): Promise<void> => {
    try {
      await api.delete(`/knowledge-bases/${kbId}/folders/${folderId}`)
    } catch (error) {
      throwApiError(error)
    }
  },

  updateFolder: async (kbId: string, folderId: string, data: { name: string }): Promise<Folder> => {
    try {
      const response = await api.put<Folder>(`/knowledge-bases/${kbId}/folders/${folderId}`, data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  // ==================== 权限管理 ====================

  getPermissions: async (kbId: string): Promise<KBPermission[]> => {
    try {
      const response = await api.get<KBPermission[]>(`/knowledge-bases/${kbId}/permissions`)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  grantPermission: async (kbId: string, data: {
    user_id: string
    role: string
    expires_at?: string
  }): Promise<KBPermission> => {
    try {
      const response = await api.post<KBPermission>(`/knowledge-bases/${kbId}/permissions`, data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  revokePermission: async (kbId: string, permissionId: string): Promise<void> => {
    try {
      await api.delete(`/knowledge-bases/${kbId}/permissions/${permissionId}`)
    } catch (error) {
      throwApiError(error)
    }
  },

  // ==================== 认证 ====================

  login: async (data: LoginRequest): Promise<AuthResponse> => {
    try {
      const response = await api.post<AuthResponse>('/auth/login', data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  register: async (data: RegisterRequest): Promise<User> => {
    try {
      const response = await api.post<User>('/auth/register', data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  getCurrentUser: async (): Promise<User> => {
    try {
      const response = await api.get<User>('/auth/me')
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  refreshToken: async (refreshToken: string): Promise<AuthResponse> => {
    try {
      const response = await api.post<AuthResponse>('/auth/refresh', { refresh_token: refreshToken })
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  changePassword: async (data: { current_password: string; new_password: string }): Promise<void> => {
    try {
      await api.put('/auth/me/password', data)
    } catch (error) {
      throwApiError(error)
    }
  },

  // ==================== 用户组管理 ====================

  listUserGroups: async (params?: { skip?: number; limit?: number; search?: string }): Promise<UserGroup[]> => {
    try {
      const response = await api.get<UserGroup[]>('/user-groups', { params })
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  getUserGroup: async (groupId: string): Promise<UserGroupDetail> => {
    try {
      const response = await api.get<UserGroupDetail>(`/user-groups/${groupId}`)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  createUserGroup: async (data: { name: string; description?: string; parent_id?: string }): Promise<UserGroup> => {
    try {
      const response = await api.post<UserGroup>('/user-groups', data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  updateUserGroup: async (groupId: string, data: { name?: string; description?: string; parent_id?: string }): Promise<UserGroup> => {
    try {
      const response = await api.put<UserGroup>(`/user-groups/${groupId}`, data)
      return response.data
    } catch (error) {
      throwApiError(error)
    }
  },

  deleteUserGroup: async (groupId: string): Promise<void> => {
    try {
      await api.delete(`/user-groups/${groupId}`)
    } catch (error) {
      throwApiError(error)
    }
  },

  addGroupMember: async (groupId: string, data: { user_id: string; is_manager: boolean }): Promise<void> => {
    try {
      await api.post(`/user-groups/${groupId}/members`, data)
    } catch (error) {
      throwApiError(error)
    }
  },

  removeGroupMember: async (groupId: string, userId: string): Promise<void> => {
    try {
      await api.delete(`/user-groups/${groupId}/members/${userId}`)
    } catch (error) {
      throwApiError(error)
    }
  },
}

export default knowledgeApi
