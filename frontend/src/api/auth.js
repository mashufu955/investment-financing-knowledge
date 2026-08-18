import request from './request'

/** 内部员工登录 */
export function login(data) {
  return request.post('/auth/login', data)
}

/** 获取当前用户信息 */
export function getMe() {
  return request.get('/auth/me')
}
