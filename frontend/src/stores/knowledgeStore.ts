import { create } from 'zustand'
import type {
  KnowledgeBase,
  KnowledgeBaseCreate,
  KnowledgeBaseUpdate,
  KnowledgeBaseStats,
  Document,
  Folder,
  SearchResult,
  SearchRequest,
} from '../types/knowledge'
import knowledgeApi from '../services/knowledgeApi'
import { getErrorMessage } from '../utils/errorHandler'

interface KnowledgeState {
  // 知识库列表
  knowledgeBases: KnowledgeBase[]
  currentKB: KnowledgeBase | null
  kbStats: KnowledgeBaseStats | null

  // 文档
  documents: Document[]
  currentDocument: Document | null

  // 文件夹
  folders: Folder[]
  currentFolder: Folder | null

  // 检索
  searchResults: SearchResult[]
  searchQuery: string
  isSearching: boolean
  searchTimeMs: number

  // UI 状态
  isLoading: boolean
  isUploading: boolean
  uploadProgress: number
  error: string | null

  // 知识库操作
  fetchKnowledgeBases: () => Promise<void>
  fetchKnowledgeBase: (id: string) => Promise<void>
  createKnowledgeBase: (data: KnowledgeBaseCreate) => Promise<KnowledgeBase>
  updateKnowledgeBase: (id: string, data: KnowledgeBaseUpdate) => Promise<void>
  deleteKnowledgeBase: (id: string) => Promise<void>

  // 文档操作
  fetchDocuments: (kbId: string, folderId?: string) => Promise<void>
  uploadDocument: (
    kbId: string,
    file: File,
    metadata?: {
      folder_id?: string
      title?: string
      author?: string
      source?: string
      tags?: string[]
    }
  ) => Promise<Document>
  deleteDocument: (docId: string) => Promise<void>

  // 检索操作
  search: (query: string, kbIds?: string[], options?: Partial<SearchRequest>) => Promise<void>
  searchKnowledgeBase: (kbId: string, query: string, options?: Partial<SearchRequest>) => Promise<void>
  clearSearch: () => void

  // 文件夹操作
  fetchFolders: (kbId: string, parentId?: string) => Promise<void>
  createFolder: (kbId: string, data: import('../types/knowledge').FolderCreate) => Promise<Folder>
  deleteFolder: (kbId: string, folderId: string) => Promise<void>
  setCurrentFolder: (folder: Folder | null) => void

  // 错误处理
  setError: (error: string | null) => void
  clearError: () => void

  // 重置状态
  reset: () => void
}

const initialState = {
  knowledgeBases: [],
  currentKB: null,
  kbStats: null,
  documents: [],
  currentDocument: null,
  folders: [],
  currentFolder: null,
  searchResults: [],
  searchQuery: '',
  isSearching: false,
  searchTimeMs: 0,
  isLoading: false,
  isUploading: false,
  uploadProgress: 0,
  error: null,
}

export const useKnowledgeStore = create<KnowledgeState>((set) => ({
  ...initialState,

  // ==================== 知识库操作 ====================

  fetchKnowledgeBases: async () => {
    set({ isLoading: true, error: null })
    try {
      const bases = await knowledgeApi.listKnowledgeBases()
      set({ knowledgeBases: bases, isLoading: false })
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isLoading: false })
    }
  },

  fetchKnowledgeBase: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      const [kb, stats] = await Promise.all([
        knowledgeApi.getKnowledgeBase(id),
        knowledgeApi.getKnowledgeBaseStats(id).catch(() => null),
      ])
      set({ currentKB: kb, kbStats: stats, isLoading: false })
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isLoading: false })
    }
  },

  createKnowledgeBase: async (data: KnowledgeBaseCreate) => {
    set({ isLoading: true, error: null })
    try {
      const newKB = await knowledgeApi.createKnowledgeBase(data)
      set((state) => ({
        knowledgeBases: [...state.knowledgeBases, newKB],
        isLoading: false,
      }))
      return newKB
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isLoading: false })
      throw new Error(errorMsg)
    }
  },

  updateKnowledgeBase: async (id: string, data: KnowledgeBaseUpdate) => {
    set({ isLoading: true, error: null })
    try {
      const updated = await knowledgeApi.updateKnowledgeBase(id, data)
      set((state) => ({
        knowledgeBases: state.knowledgeBases.map((kb) => (kb.id === id ? updated : kb)),
        currentKB: state.currentKB?.id === id ? updated : state.currentKB,
        isLoading: false,
      }))
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isLoading: false })
      throw new Error(errorMsg)
    }
  },

  deleteKnowledgeBase: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      await knowledgeApi.deleteKnowledgeBase(id)
      set((state) => ({
        knowledgeBases: state.knowledgeBases.filter((kb) => kb.id !== id),
        currentKB: state.currentKB?.id === id ? null : state.currentKB,
        kbStats: state.currentKB?.id === id ? null : state.kbStats,
        isLoading: false,
      }))
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isLoading: false })
      throw new Error(errorMsg)
    }
  },

  // ==================== 文档操作 ====================

  fetchDocuments: async (kbId: string, folderId?: string) => {
    set({ isLoading: true, error: null })
    try {
      const docs = await knowledgeApi.listDocuments(kbId, { folder_id: folderId })
      set({ documents: docs, isLoading: false })
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isLoading: false })
    }
  },

  uploadDocument: async (kbId: string, file: File, metadata?: any) => {
    set({ isUploading: true, uploadProgress: 0, error: null })
    try {
      const doc = await knowledgeApi.uploadDocument(kbId, file, metadata, (progress) => {
        set({ uploadProgress: progress })
      })
      set((state) => ({
        documents: [...state.documents, doc],
        isUploading: false,
        uploadProgress: 100,
      }))
      return doc
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isUploading: false })
      throw new Error(errorMsg)
    }
  },

  deleteDocument: async (docId: string) => {
    set({ isLoading: true, error: null })
    try {
      await knowledgeApi.deleteDocument(docId)
      set((state) => ({
        documents: state.documents.filter((d) => d.id !== docId),
        currentDocument: state.currentDocument?.id === docId ? null : state.currentDocument,
        isLoading: false,
      }))
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isLoading: false })
      throw new Error(errorMsg)
    }
  },

  // ==================== 检索操作 ====================

  search: async (query: string, kbIds?: string[], options?: Partial<SearchRequest>) => {
    set({ isSearching: true, searchQuery: query, error: null })
    try {
      const response = await knowledgeApi.search({
        query,
        kb_ids: kbIds,
        top_k: 10,
        use_rerank: true,
        ...options,
      })
      set({
        searchResults: response.results,
        searchTimeMs: response.search_time_ms,
        isSearching: false,
      })
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isSearching: false })
    }
  },

  searchKnowledgeBase: async (kbId: string, query: string, options?: Partial<SearchRequest>) => {
    set({ isSearching: true, searchQuery: query, error: null })
    try {
      const response = await knowledgeApi.searchKnowledgeBase(kbId, {
        query,
        top_k: 10,
        use_rerank: true,
        ...options,
      })
      set({
        searchResults: response.results,
        searchTimeMs: response.search_time_ms,
        isSearching: false,
      })
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isSearching: false })
    }
  },

  clearSearch: () => {
    set({ searchResults: [], searchQuery: '', searchTimeMs: 0 })
  },

  // ==================== 文件夹操作 ====================

  fetchFolders: async (kbId: string, parentId?: string) => {
    try {
      const folders = await knowledgeApi.listFolders(kbId, parentId)
      set({ folders })
    } catch (e) {
      console.error('Failed to fetch folders:', getErrorMessage(e))
    }
  },

  createFolder: async (kbId: string, data: import('../types/knowledge').FolderCreate) => {
    set({ isLoading: true, error: null })
    try {
      const folder = await knowledgeApi.createFolder(kbId, data)
      set((state) => ({
        folders: [...state.folders, folder],
        isLoading: false,
      }))
      return folder
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isLoading: false })
      throw new Error(errorMsg)
    }
  },

  deleteFolder: async (kbId: string, folderId: string) => {
    set({ isLoading: true, error: null })
    try {
      await knowledgeApi.deleteFolder(kbId, folderId)
      set((state) => ({
        folders: state.folders.filter((f) => f.id !== folderId),
        currentFolder: state.currentFolder?.id === folderId ? null : state.currentFolder,
        isLoading: false,
      }))
    } catch (e) {
      const errorMsg = getErrorMessage(e)
      set({ error: errorMsg, isLoading: false })
      throw new Error(errorMsg)
    }
  },

  setCurrentFolder: (folder: Folder | null) => {
    set({ currentFolder: folder })
  },

  // ==================== 错误处理 ====================

  setError: (error: string | null) => set({ error }),

  clearError: () => set({ error: null }),

  // ==================== 重置状态 ====================

  reset: () => set(initialState),
}))

export default useKnowledgeStore
