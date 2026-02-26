import { BrowserRouter, Routes, Route } from 'react-router-dom'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import KnowledgeBaseDetailPage from './pages/KnowledgeBaseDetailPage'
import SearchPage from './pages/SearchPage'
import LoginPage from './pages/LoginPage'
import ToastContainer from './components/Toast'

function App() {
  return (
    <BrowserRouter>
      <ToastContainer />
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/knowledge" element={<KnowledgeBasePage />} />
        <Route path="/knowledge/:id" element={<KnowledgeBaseDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
