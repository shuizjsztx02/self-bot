import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import KnowledgeBaseDetailPage from './pages/KnowledgeBaseDetailPage'
import SearchPage from './pages/SearchPage'
import LoginPage from './pages/LoginPage'
import ProtectedRoute from './components/ProtectedRoute'
import ToastContainer from './components/Toast'
import { useAuthStore, initAuth, startTokenRefreshTimer, stopTokenRefreshTimer } from './stores/authStore'

function App() {
  const [isInitializing, setIsInitializing] = useState(true)
  const { isAuthenticated } = useAuthStore()

  useEffect(() => {
    const initialize = async () => {
      await initAuth()
      setIsInitializing(false)
    }
    
    initialize()
    
    return () => {
      stopTokenRefreshTimer()
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      startTokenRefreshTimer()
    } else {
      stopTokenRefreshTimer()
    }
  }, [isAuthenticated])

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 dark:bg-slate-900">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600"></div>
          <p className="text-slate-500 dark:text-slate-400">加载中...</p>
        </div>
      </div>
    )
  }

  return (
    <BrowserRouter>
      <ToastContainer />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge"
          element={
            <ProtectedRoute>
              <KnowledgeBasePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge/:id"
          element={
            <ProtectedRoute>
              <KnowledgeBaseDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/search"
          element={
            <ProtectedRoute>
              <SearchPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
