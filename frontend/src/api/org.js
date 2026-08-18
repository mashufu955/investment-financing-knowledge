import request from './request'

// ============ 团队/基金/项目范围 ============
export function listDepartments() {
  return request.get('/org/departments')
}

export function createDepartment(data) {
  return request.post('/org/departments', data)
}

export function updateDepartment(id, data) {
  return request.put(`/org/departments/${id}`, data)
}

export function deleteDepartment(id) {
  return request.delete(`/org/departments/${id}`)
}

export function assignDepartmentMembers(id, userIds) {
  return request.post(`/org/departments/${id}/members`, userIds)
}

// ============ 内部员工 ============
export function listUsers() {
  return request.get('/org/users').catch(() => [])
}

export function createUser(data) {
  return request.post('/org/users', data)
}

export function updateUser(id, data) {
  return request.put(`/org/users/${id}`, data)
}

export function resetPassword(id, data) {
  return request.post(`/org/users/${id}/reset-password`, data)
}

export function setUserStatus(id, data) {
  return request.post(`/org/users/${id}/status`, data)
}

// ============ 角色 ============
export function listRoles() {
  return request.get('/org/roles')
}

export function createRole(data) {
  return request.post('/org/roles', data)
}

export function updateRole(id, data) {
  return request.put(`/org/roles/${id}`, data)
}

export function deleteRole(id) {
  return request.delete(`/org/roles/${id}`)
}

export function assignRolePermissions(id, permissions) {
  return request.post(`/org/roles/${id}/permissions`, { permissions })
}
