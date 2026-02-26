import { create } from 'zustand'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'
import { useEffect } from 'react'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  type: ToastType
  title: string
  message?: string
  duration?: number
}

interface ToastStore {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => string
  removeToast: (id: string) => void
  clearToasts: () => void
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }],
    }))
    return id
  },
  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }))
  },
  clearToasts: () => set({ toasts: [] }),
}))

export const toast = {
  success: (title: string, message?: string) => {
    return useToastStore.getState().addToast({ type: 'success', title, message })
  },
  error: (title: string, message?: string) => {
    return useToastStore.getState().addToast({ type: 'error', title, message })
  },
  warning: (title: string, message?: string) => {
    return useToastStore.getState().addToast({ type: 'warning', title, message })
  },
  info: (title: string, message?: string) => {
    return useToastStore.getState().addToast({ type: 'info', title, message })
  },
}

function ToastItem({ toast: t }: { toast: Toast }) {
  const { removeToast } = useToastStore()

  useEffect(() => {
    const duration = t.duration ?? 5000
    if (duration > 0) {
      const timer = setTimeout(() => {
        removeToast(t.id)
      }, duration)
      return () => clearTimeout(timer)
    }
  }, [t.id, t.duration, removeToast])

  const icons: Record<ToastType, React.ReactNode> = {
    success: <CheckCircle className="h-5 w-5 text-green-500" />,
    error: <AlertCircle className="h-5 w-5 text-red-500" />,
    warning: <AlertTriangle className="h-5 w-5 text-yellow-500" />,
    info: <Info className="h-5 w-5 text-blue-500" />,
  }

  const bgColors: Record<ToastType, string> = {
    success: 'bg-green-50 border-green-200',
    error: 'bg-red-50 border-red-200',
    warning: 'bg-yellow-50 border-yellow-200',
    info: 'bg-blue-50 border-blue-200',
  }

  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-lg border shadow-lg ${bgColors[t.type]} animate-slide-in`}
    >
      {icons[t.type]}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-900">{t.title}</p>
        {t.message && (
          <p className="mt-1 text-sm text-gray-600">{t.message}</p>
        )}
      </div>
      <button
        onClick={() => removeToast(t.id)}
        className="p-1 hover:bg-gray-200 rounded"
      >
        <X className="h-4 w-4 text-gray-400" />
      </button>
    </div>
  )
}

export default function ToastContainer() {
  const { toasts } = useToastStore()

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2 max-w-sm w-full">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  )
}
