import axios, { AxiosError } from 'axios'

export interface ApiError {
  message: string
  detail?: string
  status?: number
  code?: string
}

export function parseApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string; message?: string }>
    const status = axiosError.response?.status
    const data = axiosError.response?.data
    
    if (status === 401) {
      return {
        message: '登录已过期，请重新登录',
        detail: data?.detail,
        status,
        code: 'UNAUTHORIZED',
      }
    }
    
    if (status === 403) {
      return {
        message: '没有权限执行此操作',
        detail: data?.detail,
        status,
        code: 'FORBIDDEN',
      }
    }
    
    if (status === 404) {
      return {
        message: '请求的资源不存在',
        detail: data?.detail,
        status,
        code: 'NOT_FOUND',
      }
    }
    
    if (status === 422) {
      return {
        message: '请求参数验证失败',
        detail: data?.detail,
        status,
        code: 'VALIDATION_ERROR',
      }
    }
    
    if (status && status >= 500) {
      return {
        message: '服务器错误，请稍后重试',
        detail: data?.detail,
        status,
        code: 'SERVER_ERROR',
      }
    }
    
    return {
      message: data?.detail || data?.message || axiosError.message || '请求失败',
      detail: data?.detail,
      status,
      code: 'API_ERROR',
    }
  }
  
  if (error instanceof Error) {
    return {
      message: error.message || '未知错误',
      code: 'UNKNOWN_ERROR',
    }
  }
  
  return {
    message: '未知错误',
    code: 'UNKNOWN_ERROR',
  }
}

export function createApiError(error: unknown): Error {
  const apiError = parseApiError(error)
  const err = new Error(apiError.message)
  ;(err as any).detail = apiError.detail
  ;(err as any).status = apiError.status
  ;(err as any).code = apiError.code
  return err
}

export function throwApiError(error: unknown): never {
  throw createApiError(error)
}

export function getErrorMessage(error: unknown): string {
  return parseApiError(error).message
}
