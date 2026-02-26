export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  owner_id: string
  embedding_model: string
  chunk_size: number
  chunk_overlap: number
  department: string | null
  security_level: number
  document_count: number
  chunk_count: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseCreate {
  name: string
  description?: string
  embedding_model?: string
  chunk_size?: number
  chunk_overlap?: number
  department?: string
  security_level?: number
}

export interface KnowledgeBaseUpdate {
  name?: string
  description?: string
  embedding_model?: string
  chunk_size?: number
  chunk_overlap?: number
  department?: string
  security_level?: number
  is_active?: boolean
}

export interface KnowledgeBaseStats {
  total_documents: number
  total_chunks: number
  total_tokens: number
  by_file_type: Record<string, number>
  by_status: Record<string, number>
}

export interface Document {
  id: string
  kb_id: string
  folder_id: string | null
  filename: string
  file_type: string
  file_size: number
  title: string | null
  author: string | null
  source: string | null
  tags: string[]
  status: 'pending' | 'processing' | 'completed' | 'failed'
  current_version: number
  chunk_count: number
  token_count: number
  created_at: string
  updated_at: string
}

export interface DocumentCreate {
  kb_id: string
  file: File
  folder_id?: string
  title?: string
  author?: string
  source?: string
  tags?: string[]
}

export interface DocumentChunk {
  id: string
  doc_id: string
  chunk_index: number
  content: string
  token_count: number
  page_number: number | null
  section_title: string | null
  chunk_metadata: Record<string, unknown>
}

export interface DocumentVersion {
  id: string
  doc_id: string
  version: number
  file_path: string
  change_summary: string | null
  created_by: string | null
  created_at: string
}

export interface SearchResult {
  chunk_id: string
  doc_id: string
  doc_name: string
  kb_id: string
  kb_name: string
  content: string
  score: number
  page_number: number | null
  section_title: string | null
  extra_data: Record<string, unknown>
}

export interface SearchRequest {
  query: string
  kb_ids?: string[]
  folder_ids?: string[]
  top_k?: number
  use_rerank?: boolean
  filters?: Record<string, unknown>
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  total: number
  kb_searched: string[]
  search_time_ms: number
}

export interface Folder {
  id: string
  kb_id: string
  parent_id: string | null
  name: string
  path: string
  inherit_permissions: boolean
  created_at: string
}

export interface FolderCreate {
  name: string
  parent_id?: string
  inherit_permissions?: boolean
}

export type KBRole = 'owner' | 'admin' | 'editor' | 'viewer'

export interface KBPermission {
  id: string
  kb_id: string
  folder_id: string | null
  user_id: string | null
  group_id: string | null
  role: KBRole
  granted_by: string | null
  granted_at: string
  expires_at: string | null
}

export interface User {
  id: string
  name: string
  email: string
  department: string | null
  level: number
  is_active: boolean
  is_superuser: boolean
  created_at: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  name: string
  email: string
  password: string
  department?: string
  level?: number
}

export const ACCEPTED_FILE_TYPES = [
  '.md', '.markdown', '.txt', '.pdf', '.docx', '.doc',
  '.pptx', '.ppt', '.xlsx', '.xls'
] as const

export const FILE_TYPE_LABELS: Record<string, string> = {
  '.md': 'Markdown',
  '.markdown': 'Markdown',
  '.txt': '纯文本',
  '.pdf': 'PDF',
  '.docx': 'Word',
  '.doc': 'Word',
  '.pptx': 'PowerPoint',
  '.ppt': 'PowerPoint',
  '.xlsx': 'Excel',
  '.xls': 'Excel',
}

export const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  completed: '已完成',
  failed: '处理失败',
}

export const KB_ROLE_LABELS: Record<KBRole, string> = {
  owner: '所有者',
  admin: '管理员',
  editor: '编辑者',
  viewer: '查看者',
}

export interface HybridSearchRequest {
  query: string
  kb_id: string
  top_k?: number
  alpha?: number
  use_rerank?: boolean
}

export interface CrossHybridSearchRequest {
  query: string
  kb_ids?: string[]
  top_k?: number
  alpha?: number
  use_rerank?: boolean
}

export interface AttributionSearchRequest {
  query: string
  kb_id: string
  answer: string
  top_k?: number
  use_rerank?: boolean
  rewritten_query?: string
}

export interface SourceReference {
  chunk_id: string
  doc_id: string
  doc_name: string
  content: string
  score: number
  relevance: number
  citation: string
}

export interface RAGResponse {
  query: string
  answer: string
  sources: SourceReference[]
  overall_confidence: number
  rewritten_query: string | null
  search_time_ms: number
}

export interface CompressionSearchRequest {
  query: string
  kb_id: string
  top_k?: number
  max_tokens?: number
  use_hybrid?: boolean
}

export interface CompressedDocument {
  id: string
  original_content: string
  compressed_content: string
  relevance_score: number
  token_count: number
}

export interface CompressionSearchResponse {
  query: string
  compressed_context: string
  documents: CompressedDocument[]
  total_original_tokens: number
  total_compressed_tokens: number
  compression_ratio: number
}

export interface UserGroup {
  id: string
  name: string
  description: string | null
  parent_id: string | null
  member_count: number
  created_at: string
}

export interface UserGroupDetail extends UserGroup {
  members: GroupMember[]
}

export interface GroupMember {
  id: string
  user_id: string
  user_name: string
  user_email: string
  is_manager: boolean
  joined_at: string
}
