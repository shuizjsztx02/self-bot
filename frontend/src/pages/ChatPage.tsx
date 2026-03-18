import { useEffect, useCallback } from 'react'
import Sidebar from '../components/Sidebar'
import MessageList from '../components/MessageList'
import ChatInput from '../components/ChatInput'
import SkillInstallDialog from '../components/SkillInstallDialog'
import { useChatStore } from '../stores/chatStore'
import { chatApi } from '../services/api'

export default function ChatPage() {
  const {
    messages,
    isLoading,
    streamingContent,
    loadSettings,
    isStreaming,
    pendingSkillInstall,
    skillInstallProgress,
    setPendingSkillInstall,
    setSkillInstallProgress,
    isViewingHistory,
  } = useChatStore()

  useEffect(() => {
    loadSettings()
  }, [])

  const handleConfirmInstall = useCallback(
    async (options: {
      install_pip: boolean
      install_npm: boolean
      install_mcp: boolean
      install_bins: boolean
      env_vars: Record<string, string>
    }) => {
      if (!pendingSkillInstall) return

      await chatApi.confirmSkillInstall(
        {
          skill_slug: pendingSkillInstall.skillSlug,
          ...options,
        },
        (event) => {
          if (event.type === 'skill_install_progress') {
            setSkillInstallProgress({
              step: event.step,
              detail: event.detail,
              progress: event.progress,
            })
          } else if (event.type === 'skill_ready') {
            setPendingSkillInstall(null)
            setSkillInstallProgress(null)
            useChatStore.setState((state) => ({
              messages: [
                ...state.messages,
                {
                  id: `skill_ready_${Date.now()}`,
                  role: 'assistant' as const,
                  content: `✅ ${event.skill_name || '技能'}: ${event.message || '依赖安装完成，技能已激活。请重新发送您的请求以使用该技能。'}`,
                  created_at: new Date().toISOString(),
                },
              ],
            }))
          } else if (event.type === 'skill_install_failed' || event.type === 'error') {
            setSkillInstallProgress(null)
            useChatStore.setState((state) => ({
              messages: [
                ...state.messages,
                {
                  id: `skill_fail_${Date.now()}`,
                  role: 'assistant' as const,
                  content: `❌ ${event.skill_name || '技能'}: ${event.message || event.error || '依赖安装失败'}`,
                  created_at: new Date().toISOString(),
                },
              ],
            }))
          }
        },
      )
    },
    [pendingSkillInstall, setPendingSkillInstall, setSkillInstallProgress],
  )

  const handleCancelInstall = useCallback(() => {
    setPendingSkillInstall(null)
    setSkillInstallProgress(null)
  }, [setPendingSkillInstall, setSkillInstallProgress])

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <MessageList
          messages={messages}
          isLoading={isLoading}
          streamingContent={isStreaming ? streamingContent : undefined}
          isViewingHistory={isViewingHistory}
        />
        <ChatInput />
      </div>

      {pendingSkillInstall && (
        <SkillInstallDialog
          data={pendingSkillInstall}
          installProgress={skillInstallProgress}
          onConfirm={handleConfirmInstall}
          onCancel={handleCancelInstall}
        />
      )}
    </div>
  )
}
