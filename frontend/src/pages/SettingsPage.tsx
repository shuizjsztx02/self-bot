import { useEffect, useState } from 'react'
import { useChatStore } from '../stores/chatStore'
import { ArrowLeft, Check, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Settings } from '../types'

export default function SettingsPage() {
  const { settings, loadSettings } = useChatStore()
  const [localSettings, setLocalSettings] = useState<Settings | null>(null)

  useEffect(() => {
    loadSettings()
  }, [])

  useEffect(() => {
    setLocalSettings(settings)
  }, [settings])

  if (!localSettings) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-slate-500">加载中...</div>
      </div>
    )
  }

  return (
    <div className="flex h-screen">
      <div className="w-64 border-r border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-700">
          <h1 className="text-lg font-bold text-primary-600 dark:text-primary-400">
            Self-Bot
          </h1>
        </div>
      </div>

      <div className="flex flex-1 flex-col">
        <div className="flex items-center gap-4 border-b border-slate-200 p-4 dark:border-slate-700">
          <Link
            to="/"
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700"
          >
            <ArrowLeft size={20} />
          </Link>
          <h2 className="text-xl font-semibold text-slate-800 dark:text-white">
            设置
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-2xl space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
              <h3 className="mb-4 text-lg font-medium text-slate-800 dark:text-white">
                模型提供商
              </h3>
              <div className="space-y-3">
                {localSettings.providers.map((provider) => (
                  <div
                    key={provider.name}
                    className="flex items-center justify-between rounded-lg border border-slate-200 p-4 dark:border-slate-600"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`h-3 w-3 rounded-full ${
                          provider.available ? 'bg-green-500' : 'bg-red-500'
                        }`}
                      />
                      <div>
                        <div className="font-medium text-slate-800 dark:text-white">
                          {provider.name.toUpperCase()}
                        </div>
                        <div className="text-sm text-slate-500 dark:text-slate-400">
                          {provider.model}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {provider.available ? (
                        <Check size={18} className="text-green-500" />
                      ) : (
                        <X size={18} className="text-red-500" />
                      )}
                      <span className="text-sm text-slate-500 dark:text-slate-400">
                        {provider.available ? '可用' : '未配置'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
              <h3 className="mb-4 text-lg font-medium text-slate-800 dark:text-white">
                默认提供商
              </h3>
              <div className="rounded-lg border border-primary-200 bg-primary-50 p-4 dark:border-primary-800 dark:bg-primary-900/20">
                <span className="font-medium text-primary-700 dark:text-primary-300">
                  {localSettings.default_provider.toUpperCase()}
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
              <h3 className="mb-4 text-lg font-medium text-slate-800 dark:text-white">
                环境变量配置
              </h3>
              <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                <p>请在后端 <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-700">.env</code> 文件中配置以下变量：</p>
                <ul className="list-inside list-disc space-y-1">
                  <li><code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-700">OPENAI_API_KEY</code> - OpenAI API密钥</li>
                  <li><code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-700">ANTHROPIC_API_KEY</code> - Claude API密钥</li>
                  <li><code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-700">DEEPSEEK_API_KEY</code> - DeepSeek API密钥</li>
                  <li><code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-700">OLLAMA_BASE_URL</code> - Ollama服务地址</li>
                  <li><code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-700">DEFAULT_LLM_PROVIDER</code> - 默认提供商</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
