import { useState } from 'react'
import { X, Package, Server, Key, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import clsx from 'clsx'

interface MissingDeps {
  missing_pip: string[]
  missing_npm: string[]
  missing_mcp_servers: { name: string; module?: string }[]
  missing_tools: string[]
  missing_env_vars: string[]
  missing_bins: string[]
}

export interface PendingSkillInstall {
  visible: boolean
  skillName: string
  skillSlug: string
  missing: MissingDeps
  message: string
}

interface SkillInstallDialogProps {
  data: PendingSkillInstall
  installProgress: { step: string; detail: string; progress: number } | null
  onConfirm: (options: {
    install_pip: boolean
    install_npm: boolean
    install_mcp: boolean
    install_bins: boolean
    env_vars: Record<string, string>
  }) => void
  onCancel: () => void
}

export default function SkillInstallDialog({
  data,
  installProgress,
  onConfirm,
  onCancel,
}: SkillInstallDialogProps) {
  const [installPip, setInstallPip] = useState(true)
  const [installNpm, setInstallNpm] = useState(true)
  const [installMcp, setInstallMcp] = useState(true)
  const [installBins, setInstallBins] = useState(true)
  const [envValues, setEnvValues] = useState<Record<string, string>>({})
  const [isInstalling, setIsInstalling] = useState(false)

  if (!data.visible) return null

  const { missing } = data
  const hasPip = missing.missing_pip.length > 0
  const hasNpm = missing.missing_npm.length > 0
  const hasMcp = missing.missing_mcp_servers.length > 0
  const hasEnv = missing.missing_env_vars.length > 0
  const hasTools = missing.missing_tools.length > 0
  const hasBins = (missing.missing_bins ?? []).length > 0

  const handleConfirm = () => {
    setIsInstalling(true)
    onConfirm({
      install_pip: installPip,
      install_npm: installNpm,
      install_mcp: installMcp,
      install_bins: installBins,
      env_vars: envValues,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="relative mx-4 w-full max-w-lg rounded-xl bg-white shadow-2xl dark:bg-gray-800">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
              <Package className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {data.skillName}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                需要安装依赖才能使用
              </p>
            </div>
          </div>
          <button
            onClick={onCancel}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
          {/* pip packages */}
          {hasPip && (
            <DependencySection
              title="Python 包"
              icon={<Package className="h-4 w-4" />}
              items={missing.missing_pip}
              checked={installPip}
              onToggle={setInstallPip}
              disabled={isInstalling}
            />
          )}

          {/* npm packages */}
          {hasNpm && (
            <DependencySection
              title="Node.js 包"
              icon={<Package className="h-4 w-4" />}
              items={missing.missing_npm}
              checked={installNpm}
              onToggle={setInstallNpm}
              disabled={isInstalling}
            />
          )}

          {/* MCP servers */}
          {hasMcp && (
            <DependencySection
              title="MCP 服务"
              icon={<Server className="h-4 w-4" />}
              items={missing.missing_mcp_servers.map((s) => s.name)}
              checked={installMcp}
              onToggle={setInstallMcp}
              disabled={isInstalling}
            />
          )}

          {/* Environment variables */}
          {hasEnv && (
            <div className="mb-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                <Key className="h-4 w-4" />
                <span>环境变量（需手动填写）</span>
              </div>
              <div className="space-y-2 rounded-lg bg-gray-50 p-3 dark:bg-gray-700/50">
                {missing.missing_env_vars.map((v) => (
                  <div key={v} className="flex items-center gap-2">
                    <label className="w-48 shrink-0 text-xs font-mono text-gray-600 dark:text-gray-400">
                      {v}
                    </label>
                    <input
                      type="password"
                      placeholder="请输入..."
                      value={envValues[v] || ''}
                      onChange={(e) =>
                        setEnvValues((prev) => ({ ...prev, [v]: e.target.value }))
                      }
                      disabled={isInstalling}
                      className="w-full rounded-md border border-gray-300 px-2 py-1 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* bins (可自动安装) */}
          {hasBins && (
            <DependencySection
              title="系统命令（可通过 brew/scoop 自动安装）"
              icon={<Package className="h-4 w-4" />}
              items={missing.missing_bins}
              checked={installBins}
              onToggle={setInstallBins}
              disabled={isInstalling}
            />
          )}

          {/* Missing tools (info only) */}
          {hasTools && (
            <div className="mb-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-600 dark:text-amber-400">
                <AlertCircle className="h-4 w-4" />
                <span>缺失工具（需要对应 MCP 服务提供）</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {missing.missing_tools.map((t) => (
                  <span
                    key={t}
                    className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-mono text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Progress */}
          {isInstalling && installProgress && (
            <div className="mt-4 rounded-lg bg-blue-50 p-3 dark:bg-blue-900/30">
              <div className="mb-2 flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>{installProgress.detail}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-blue-200 dark:bg-blue-800">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all duration-300"
                  style={{ width: `${Math.round(installProgress.progress * 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700">
          <button
            onClick={onCancel}
            disabled={isInstalling}
            className="rounded-lg px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            跳过
          </button>
          <button
            onClick={handleConfirm}
            disabled={isInstalling}
            className={clsx(
              'flex items-center gap-2 rounded-lg px-5 py-2 text-sm font-medium text-white transition-colors',
              isInstalling
                ? 'cursor-not-allowed bg-blue-400'
                : 'bg-blue-600 hover:bg-blue-700'
            )}
          >
            {isInstalling ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                安装中...
              </>
            ) : (
              <>
                <CheckCircle className="h-4 w-4" />
                确认安装
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

function DependencySection({
  title,
  icon,
  items,
  checked,
  onToggle,
  disabled,
}: {
  title: string
  icon: React.ReactNode
  items: string[]
  checked: boolean
  onToggle: (v: boolean) => void
  disabled: boolean
}) {
  return (
    <div className="mb-4">
      <label className="mb-2 flex cursor-pointer items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onToggle(e.target.checked)}
          disabled={disabled}
          className="rounded border-gray-300 text-blue-600"
        />
        {icon}
        <span>{title}</span>
      </label>
      <div className="flex flex-wrap gap-1.5 pl-6">
        {items.map((item) => (
          <span
            key={item}
            className="rounded-md bg-gray-100 px-2 py-0.5 text-xs font-mono text-gray-700 dark:bg-gray-700 dark:text-gray-300"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}
