import { useEffect } from 'react'
import Sidebar from '../components/Sidebar'
import MessageList from '../components/MessageList'
import ChatInput from '../components/ChatInput'
import { useChatStore } from '../stores/chatStore'

export default function ChatPage() {
  const { messages, isLoading, streamingContent, loadSettings, isStreaming } = useChatStore()

  useEffect(() => {
    loadSettings()
  }, [])

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <MessageList
          messages={messages}
          isLoading={isLoading}
          streamingContent={isStreaming ? streamingContent : undefined}
        />
        <ChatInput />
      </div>
    </div>
  )
}
