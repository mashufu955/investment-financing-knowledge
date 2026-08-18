import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    accessToken: localStorage.getItem('access_token') || '',
    userInfo: JSON.parse(localStorage.getItem('user_info') || 'null'),
    permissions: JSON.parse(localStorage.getItem('permissions') || '[]'),
  }),
  getters: {
    isLoggedIn: (s) => Boolean(s.accessToken),
  },
  actions: {
    /** 登录成功后保存会话 */
    setSession({ access_token, user_info, permissions }) {
      this.accessToken = access_token
      this.userInfo = user_info
      this.permissions = permissions || []
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('user_info', JSON.stringify(user_info))
      localStorage.setItem('permissions', JSON.stringify(permissions || []))
    },
    /** 退出登录 */
    clearSession() {
      this.accessToken = ''
      this.userInfo = null
      this.permissions = []
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_info')
      localStorage.removeItem('permissions')
    },
    /** 是否有指定操作权限 */
    hasPermission(code) {
      return this.permissions.includes(code)
    },
  },
})
