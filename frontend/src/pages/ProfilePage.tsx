import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Save, AlertCircle, CheckCircle, Lock, Key, MessageSquare } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { knowledgeApi } from '../services/knowledgeApi'
import { toast } from '../components/Toast'
import Sidebar from '../components/Sidebar'

interface UserProfile {
  name: string
  email: string
  department: string
  level: number
}

interface PasswordForm {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

export default function ProfilePage() {
  const navigate = useNavigate()
  const { user, setUser } = useAuthStore()
  const [isSaving, setIsSaving] = useState(false)
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  
  const [profile, setProfile] = useState<UserProfile>({
    name: '',
    email: '',
    department: '',
    level: 1,
  })
  
  const [passwordForm, setPasswordForm] = useState<PasswordForm>({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  })
  
  const [errors, setErrors] = useState<{ name?: string; department?: string; level?: string }>({})
  const [passwordErrors, setPasswordErrors] = useState<{ currentPassword?: string; newPassword?: string; confirmPassword?: string }>({})

  useEffect(() => {
    if (user) {
      setProfile({
        name: user.name || '',
        email: user.email || '',
        department: user.department || '',
        level: user.level || 1,
      })
    }
  }, [user])

  const validateName = (value: string): string | undefined => {
    if (!value.trim()) return '请输入姓名'
    if (value.length < 1) return '姓名至少需要1个字符'
    if (value.length > 100) return '姓名不能超过100个字符'
    return undefined
  }

  const validateDepartment = (value: string): string | undefined => {
    if (value && value.length > 100) return '部门名称不能超过100个字符'
    return undefined
  }

  const validateLevel = (value: number): string | undefined => {
    if (value < 1 || value > 4) return '级别必须在1-4之间'
    return undefined
  }

  const validateCurrentPassword = (value: string): string | undefined => {
    if (!value) return '请输入当前密码'
    if (value.length < 6) return '密码至少需要6个字符'
    return undefined
  }

  const validateNewPassword = (value: string): string | undefined => {
    if (!value) return '请输入新密码'
    if (value.length < 6) return '密码至少需要6个字符'
    if (value.length > 100) return '密码不能超过100个字符'
    return undefined
  }

  const validateConfirmPassword = (value: string, newPassword: string): string | undefined => {
    if (!value) return '请确认新密码'
    if (value !== newPassword) return '两次输入的密码不一致'
    return undefined
  }

  const handleNameChange = (value: string) => {
    setProfile(prev => ({ ...prev, name: value }))
    setErrors(prev => ({ ...prev, name: validateName(value) }))
  }

  const handleDepartmentChange = (value: string) => {
    setProfile(prev => ({ ...prev, department: value }))
    setErrors(prev => ({ ...prev, department: validateDepartment(value) }))
  }

  const handleLevelChange = (value: number) => {
    setProfile(prev => ({ ...prev, level: value }))
    setErrors(prev => ({ ...prev, level: validateLevel(value) }))
  }

  const handlePasswordChange = (field: keyof PasswordForm, value: string) => {
    setPasswordForm(prev => ({ ...prev, [field]: value }))
    
    if (field === 'currentPassword') {
      setPasswordErrors(prev => ({ ...prev, currentPassword: validateCurrentPassword(value) }))
    } else if (field === 'newPassword') {
      setPasswordErrors(prev => ({ 
        ...prev, 
        newPassword: validateNewPassword(value),
        confirmPassword: validateConfirmPassword(passwordForm.confirmPassword, value)
      }))
    } else if (field === 'confirmPassword') {
      setPasswordErrors(prev => ({ ...prev, confirmPassword: validateConfirmPassword(value, passwordForm.newPassword) }))
    }
  }

  const validateForm = (): boolean => {
    const newErrors = {
      name: validateName(profile.name),
      department: validateDepartment(profile.department),
      level: validateLevel(profile.level),
    }
    setErrors(newErrors)
    return !Object.values(newErrors).some(Boolean)
  }

  const validatePasswordForm = (): boolean => {
    const newErrors = {
      currentPassword: validateCurrentPassword(passwordForm.currentPassword),
      newPassword: validateNewPassword(passwordForm.newPassword),
      confirmPassword: validateConfirmPassword(passwordForm.confirmPassword, passwordForm.newPassword),
    }
    setPasswordErrors(newErrors)
    return !Object.values(newErrors).some(Boolean)
  }

  const handleSave = async () => {
    if (!validateForm()) {
      toast.error('验证失败', '请检查表单中的错误')
      return
    }

    setIsSaving(true)
    try {
      const updatedUser = await knowledgeApi.updateProfile({
        name: profile.name.trim(),
        department: profile.department.trim() || undefined,
        level: profile.level,
      })
      
      setUser(updatedUser)
      toast.success('保存成功', '个人资料已更新')
    } catch (error: any) {
      const detail = error.response?.data?.detail
      toast.error('保存失败', detail || error.message || '操作失败')
    } finally {
      setIsSaving(false)
    }
  }

  const handleChangePassword = async () => {
    if (!validatePasswordForm()) {
      toast.error('验证失败', '请检查表单中的错误')
      return
    }

    setIsChangingPassword(true)
    try {
      await knowledgeApi.changePassword({
        current_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword,
      })
      
      toast.success('密码修改成功', '请使用新密码登录')
      setPasswordForm({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      })
    } catch (error: any) {
      const detail = error.response?.data?.detail
      toast.error('密码修改失败', detail || error.message || '操作失败')
    } finally {
      setIsChangingPassword(false)
    }
  }

  const getInputStatus = (value: string, error?: string) => {
    if (!value) return 'default'
    if (error) return 'error'
    return 'success'
  }

  return (
    <div className="flex h-screen bg-slate-100 dark:bg-slate-900">
      <Sidebar />
      
      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-2xl p-6">
          <div className="mb-6 flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-2 text-gray-600 hover:text-primary-600 transition-colors dark:text-slate-400 dark:hover:text-primary-400"
              title="返回聊天"
            >
              <MessageSquare className="h-5 w-5" />
              <span className="text-sm font-medium">返回聊天</span>
            </button>
            <div className="h-6 w-px bg-gray-200 dark:bg-slate-600" />
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                个人资料
              </h1>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                管理您的账户信息
              </p>
            </div>
          </div>

          <div className="rounded-lg bg-white p-6 shadow dark:bg-slate-800">
            <div className="mb-6 flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/30">
                <User size={32} className="text-primary-600 dark:text-primary-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                  {profile.name || '用户'}
                </h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {profile.email}
                </p>
              </div>
            </div>

            <div className="space-y-6">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  姓名 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={profile.name}
                    onChange={(e) => handleNameChange(e.target.value)}
                    className={`w-full rounded-lg border px-4 py-2 pr-10 focus:outline-none dark:bg-slate-700 dark:text-white ${
                      getInputStatus(profile.name, errors.name) === 'error'
                        ? 'border-red-500 focus:border-red-500'
                        : getInputStatus(profile.name, errors.name) === 'success'
                        ? 'border-green-500 focus:border-green-500'
                        : 'border-slate-300 focus:border-primary-500 dark:border-slate-600'
                    }`}
                    placeholder="请输入姓名"
                  />
                  {profile.name && (
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

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  邮箱
                </label>
                <input
                  type="email"
                  value={profile.email}
                  disabled
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-slate-500 dark:border-slate-600 dark:bg-slate-600 dark:text-slate-400"
                />
                <p className="mt-1 text-xs text-slate-500">邮箱不可修改</p>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  部门
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={profile.department}
                    onChange={(e) => handleDepartmentChange(e.target.value)}
                    className={`w-full rounded-lg border px-4 py-2 pr-10 focus:outline-none dark:bg-slate-700 dark:text-white ${
                      getInputStatus(profile.department, errors.department) === 'error'
                        ? 'border-red-500 focus:border-red-500'
                        : profile.department
                        ? 'border-green-500 focus:border-green-500'
                        : 'border-slate-300 focus:border-primary-500 dark:border-slate-600'
                    }`}
                    placeholder="请输入部门名称（可选）"
                  />
                  {profile.department && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      {errors.department ? (
                        <AlertCircle size={18} className="text-red-500" />
                      ) : (
                        <CheckCircle size={18} className="text-green-500" />
                      )}
                    </div>
                  )}
                </div>
                {errors.department && (
                  <p className="mt-1 text-sm text-red-500">{errors.department}</p>
                )}
                <p className="mt-1 text-xs text-slate-500">部门名称最多100个字符</p>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  级别
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="1"
                    max="4"
                    value={profile.level}
                    onChange={(e) => handleLevelChange(parseInt(e.target.value))}
                    className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 dark:bg-slate-600"
                  />
                  <span className="w-8 rounded-lg bg-primary-100 px-2 py-1 text-center text-sm font-medium text-primary-600 dark:bg-primary-900/30 dark:text-primary-400">
                    {profile.level}
                  </span>
                </div>
                {errors.level && (
                  <p className="mt-1 text-sm text-red-500">{errors.level}</p>
                )}
                <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-600 dark:bg-slate-700/50">
                  <p className="mb-2 text-xs font-medium text-slate-600 dark:text-slate-400">级别权限说明：</p>
                  <div className="space-y-1 text-xs text-slate-500 dark:text-slate-400">
                    <div className="flex items-center gap-2">
                      <span className="inline-block w-6 rounded bg-gray-200 px-1 text-center font-medium dark:bg-gray-600">1</span>
                      <span>查看者 (Viewer) - 只读访问知识库内容</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="inline-block w-6 rounded bg-blue-100 px-1 text-center font-medium text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">2</span>
                      <span>编辑者 (Editor) - 可创建、编辑、删除文档</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="inline-block w-6 rounded bg-orange-100 px-1 text-center font-medium text-orange-700 dark:bg-orange-900/50 dark:text-orange-300">3</span>
                      <span>管理员 (Admin) - 可管理权限、编辑内容</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="inline-block w-6 rounded bg-purple-100 px-1 text-center font-medium text-purple-700 dark:bg-purple-900/50 dark:text-purple-300">4</span>
                      <span>所有者 (Owner) - 完全控制，可删除知识库</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-4">
                <button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="flex items-center gap-2 rounded-lg bg-primary-600 px-6 py-2 text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {isSaving ? (
                    <>
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                      <span>保存中...</span>
                    </>
                  ) : (
                    <>
                      <Save size={18} />
                      <span>保存修改</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-lg bg-white p-6 shadow dark:bg-slate-800">
            <div className="mb-4 flex items-center gap-2">
              <Lock size={20} className="text-slate-600 dark:text-slate-400" />
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                修改密码
              </h3>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  当前密码 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="password"
                    value={passwordForm.currentPassword}
                    onChange={(e) => handlePasswordChange('currentPassword', e.target.value)}
                    className={`w-full rounded-lg border px-4 py-2 pr-10 focus:outline-none dark:bg-slate-700 dark:text-white ${
                      getInputStatus(passwordForm.currentPassword, passwordErrors.currentPassword) === 'error'
                        ? 'border-red-500 focus:border-red-500'
                        : passwordForm.currentPassword
                        ? 'border-green-500 focus:border-green-500'
                        : 'border-slate-300 focus:border-primary-500 dark:border-slate-600'
                    }`}
                    placeholder="请输入当前密码"
                  />
                  {passwordForm.currentPassword && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      {passwordErrors.currentPassword ? (
                        <AlertCircle size={18} className="text-red-500" />
                      ) : (
                        <CheckCircle size={18} className="text-green-500" />
                      )}
                    </div>
                  )}
                </div>
                {passwordErrors.currentPassword && (
                  <p className="mt-1 text-sm text-red-500">{passwordErrors.currentPassword}</p>
                )}
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  新密码 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="password"
                    value={passwordForm.newPassword}
                    onChange={(e) => handlePasswordChange('newPassword', e.target.value)}
                    className={`w-full rounded-lg border px-4 py-2 pr-10 focus:outline-none dark:bg-slate-700 dark:text-white ${
                      getInputStatus(passwordForm.newPassword, passwordErrors.newPassword) === 'error'
                        ? 'border-red-500 focus:border-red-500'
                        : passwordForm.newPassword
                        ? 'border-green-500 focus:border-green-500'
                        : 'border-slate-300 focus:border-primary-500 dark:border-slate-600'
                    }`}
                    placeholder="请输入新密码（至少6位）"
                  />
                  {passwordForm.newPassword && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      {passwordErrors.newPassword ? (
                        <AlertCircle size={18} className="text-red-500" />
                      ) : (
                        <CheckCircle size={18} className="text-green-500" />
                      )}
                    </div>
                  )}
                </div>
                {passwordErrors.newPassword && (
                  <p className="mt-1 text-sm text-red-500">{passwordErrors.newPassword}</p>
                )}
                <p className="mt-1 text-xs text-slate-500">密码长度为6-100个字符</p>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  确认新密码 <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="password"
                    value={passwordForm.confirmPassword}
                    onChange={(e) => handlePasswordChange('confirmPassword', e.target.value)}
                    className={`w-full rounded-lg border px-4 py-2 pr-10 focus:outline-none dark:bg-slate-700 dark:text-white ${
                      getInputStatus(passwordForm.confirmPassword, passwordErrors.confirmPassword) === 'error'
                        ? 'border-red-500 focus:border-red-500'
                        : passwordForm.confirmPassword
                        ? 'border-green-500 focus:border-green-500'
                        : 'border-slate-300 focus:border-primary-500 dark:border-slate-600'
                    }`}
                    placeholder="请再次输入新密码"
                  />
                  {passwordForm.confirmPassword && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      {passwordErrors.confirmPassword ? (
                        <AlertCircle size={18} className="text-red-500" />
                      ) : (
                        <CheckCircle size={18} className="text-green-500" />
                      )}
                    </div>
                  )}
                </div>
                {passwordErrors.confirmPassword && (
                  <p className="mt-1 text-sm text-red-500">{passwordErrors.confirmPassword}</p>
                )}
              </div>

              <div className="flex justify-end pt-4">
                <button
                  onClick={handleChangePassword}
                  disabled={isChangingPassword}
                  className="flex items-center gap-2 rounded-lg bg-slate-600 px-6 py-2 text-white hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-700 dark:hover:bg-slate-600"
                >
                  {isChangingPassword ? (
                    <>
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                      <span>修改中...</span>
                    </>
                  ) : (
                    <>
                      <Key size={18} />
                      <span>修改密码</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
