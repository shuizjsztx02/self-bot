import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogIn, UserPlus, AlertCircle, CheckCircle } from 'lucide-react'
import { knowledgeApi } from '../services/knowledgeApi'
import { toast } from '../components/Toast'

export default function LoginPage() {
  const navigate = useNavigate()
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errors, setErrors] = useState<{ name?: string; email?: string; password?: string }>({})

  const validateName = (value: string): string | undefined => {
    if (!value.trim()) return '请输入姓名'
    if (value.length < 1) return '姓名至少需要1个字符'
    if (value.length > 100) return '姓名不能超过100个字符'
    return undefined
  }

  const validateEmail = (value: string): string | undefined => {
    if (!value.trim()) return '请输入邮箱'
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(value)) return '请输入有效的邮箱地址'
    return undefined
  }

  const validatePassword = (value: string): string | undefined => {
    if (!value) return '请输入密码'
    if (value.length < 6) return '密码至少需要6个字符'
    if (value.length > 100) return '密码不能超过100个字符'
    return undefined
  }

  const handleNameChange = (value: string) => {
    setName(value)
    if (!isLogin) {
      setErrors(prev => ({ ...prev, name: validateName(value) }))
    }
  }

  const handleEmailChange = (value: string) => {
    setEmail(value)
    setErrors(prev => ({ ...prev, email: validateEmail(value) }))
  }

  const handlePasswordChange = (value: string) => {
    setPassword(value)
    setErrors(prev => ({ ...prev, password: validatePassword(value) }))
  }

  const validateForm = (): boolean => {
    const newErrors: { name?: string; email?: string; password?: string } = {}
    
    if (!isLogin) {
      newErrors.name = validateName(name)
    }
    newErrors.email = validateEmail(email)
    newErrors.password = validatePassword(password)
    
    setErrors(newErrors)
    return !Object.values(newErrors).some(Boolean)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) {
      toast.error('验证失败', '请检查表单中的错误')
      return
    }
    
    setIsLoading(true)

    try {
      if (isLogin) {
        const response = await knowledgeApi.login({ email, password })
        localStorage.setItem('token', response.access_token)
        if (response.refresh_token) {
          localStorage.setItem('refreshToken', response.refresh_token)
        }
        toast.success('登录成功', '欢迎回来！')
        navigate('/knowledge')
      } else {
        await knowledgeApi.register({ name: name.trim(), email: email.trim(), password })
        toast.success('注册成功', '请登录')
        setIsLogin(true)
        setPassword('')
      }
    } catch (error: any) {
      const detail = error.response?.data?.detail
      let message = error.message || '操作失败'
      
      if (typeof detail === 'string') {
        message = detail
      } else if (Array.isArray(detail)) {
        message = detail.map((d: any) => d.msg || d.message).join(', ')
      }
      
      toast.error(isLogin ? '登录失败' : '注册失败', message)
    } finally {
      setIsLoading(false)
    }
  }

  const getInputStatus = (value: string, error?: string) => {
    if (!value) return 'default'
    if (error) return 'error'
    return 'success'
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 dark:bg-slate-900">
      <div className="w-full max-w-md">
        <div className="rounded-lg bg-white p-8 shadow-lg dark:bg-slate-800">
          <h1 className="mb-6 text-center text-2xl font-bold text-slate-900 dark:text-white">
            {isLogin ? '登录' : '注册'}
          </h1>

          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  姓名 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => handleNameChange(e.target.value)}
                    className={`w-full rounded-lg border px-4 py-2 pr-10 focus:outline-none dark:bg-slate-700 dark:text-white ${
                      getInputStatus(name, errors.name) === 'error' 
                        ? 'border-red-500 focus:border-red-500' 
                        : getInputStatus(name, errors.name) === 'success'
                        ? 'border-green-500 focus:border-green-500'
                        : 'border-slate-300 focus:border-primary-500 dark:border-slate-600'
                    }`}
                    placeholder="请输入姓名（1-100字符）"
                  />
                  {name && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      {errors.name ? (
                        <AlertCircle size={18} className="text-red-500" />
                      ) : (
                        <CheckCircle size={18} className="text-green-500" />
                      )}
                    </div>
                  )}
                </div>
                {errors.name && (
                  <p className="mt-1 text-sm text-red-500">{errors.name}</p>
                )}
                <p className="mt-1 text-xs text-slate-500">姓名长度为1-100个字符</p>
              </div>
            )}

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                邮箱 <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => handleEmailChange(e.target.value)}
                  className={`w-full rounded-lg border px-4 py-2 pr-10 focus:outline-none dark:bg-slate-700 dark:text-white ${
                    getInputStatus(email, errors.email) === 'error' 
                      ? 'border-red-500 focus:border-red-500' 
                      : getInputStatus(email, errors.email) === 'success'
                      ? 'border-green-500 focus:border-green-500'
                      : 'border-slate-300 focus:border-primary-500 dark:border-slate-600'
                  }`}
                  placeholder="请输入有效邮箱地址"
                />
                {email && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {errors.email ? (
                      <AlertCircle size={18} className="text-red-500" />
                    ) : (
                      <CheckCircle size={18} className="text-green-500" />
                    )}
                  </div>
                )}
              </div>
              {errors.email && (
                <p className="mt-1 text-sm text-red-500">{errors.email}</p>
              )}
              <p className="mt-1 text-xs text-slate-500">请输入有效的邮箱格式，如 example@domain.com</p>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                密码 <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => handlePasswordChange(e.target.value)}
                  className={`w-full rounded-lg border px-4 py-2 pr-10 focus:outline-none dark:bg-slate-700 dark:text-white ${
                    getInputStatus(password, errors.password) === 'error' 
                      ? 'border-red-500 focus:border-red-500' 
                      : getInputStatus(password, errors.password) === 'success'
                      ? 'border-green-500 focus:border-green-500'
                      : 'border-slate-300 focus:border-primary-500 dark:border-slate-600'
                  }`}
                  placeholder="请输入密码（至少6位）"
                />
                {password && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {errors.password ? (
                      <AlertCircle size={18} className="text-red-500" />
                    ) : (
                      <CheckCircle size={18} className="text-green-500" />
                    )}
                  </div>
                )}
              </div>
              {errors.password && (
                <p className="mt-1 text-sm text-red-500">{errors.password}</p>
              )}
              <p className="mt-1 text-xs text-slate-500">密码长度为6-100个字符</p>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white hover:bg-primary-700 disabled:opacity-50"
            >
              {isLoading ? (
                <span>处理中...</span>
              ) : isLogin ? (
                <>
                  <LogIn className="h-4 w-4" />
                  <span>登录</span>
                </>
              ) : (
                <>
                  <UserPlus className="h-4 w-4" />
                  <span>注册</span>
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-slate-600 dark:text-slate-400">
            {isLogin ? (
              <p>
                还没有账号？{' '}
                <button
                  onClick={() => {
                    setIsLogin(false)
                    setErrors({})
                  }}
                  className="text-primary-600 hover:underline"
                >
                  立即注册
                </button>
              </p>
            ) : (
              <p>
                已有账号？{' '}
                <button
                  onClick={() => {
                    setIsLogin(true)
                    setErrors({})
                  }}
                  className="text-primary-600 hover:underline"
                >
                  立即登录
                </button>
              </p>
            )}
          </div>

          <div className="mt-4 text-center">
            <button
              onClick={() => navigate('/')}
              className="text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400"
            >
              返回首页
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
