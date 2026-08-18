import request from './request'

/** 导入项目文档（单文件/批量） */
export function importDocuments(files) {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  return request.post('/knowledge/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000, // 文件落盘可能需要更长时间
  })
}

/** 分页查询知识单元 */
export function listUnits(params) {
  return request.get('/knowledge/units', { params })
}

/** 查询单元详情 */
export function getUnit(id) {
  return request.get(`/knowledge/units/${id}`)
}

/** 更新知识单元 */
export function updateUnit(id, data) {
  return request.put(`/knowledge/units/${id}`, data)
}

/** 批量删除知识单元 */
export function deleteUnits(unitIds) {
  return request.delete('/knowledge/units', { data: unitIds })
}

/** 配置单元数据权限 */
export function configureUnitPermissions(id, entities) {
  return request.post(`/knowledge/units/${id}/permissions`, { entities })
}

/** 批量校验数据权限 */
export function checkPermissions(data) {
  return request.post('/knowledge/check-permissions', data)
}

/** 轮询导入任务进度 */
export function pollImportProgress(taskId) {
  return request.get(`/knowledge/import/${taskId}`)
}

/** 批量删除知识单元 */
export function batchDeleteUnits(unitIds) {
  return deleteUnits(unitIds)
}
