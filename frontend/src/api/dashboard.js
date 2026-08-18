import request from './request'

/** 核心指标：访问次数/独立用户/知识单元数/Token 总量/平均耗时 */
export function getMetrics() {
  return request.get('/dashboard/metrics')
}

/** 项目阶段漏斗、融资金额与行业分布 */
export function getProjectPipeline() {
  return request.get('/dashboard/project-pipeline')
}

/** 投融资常见问题 TOP 榜 */
export function getQuestionRankings(topN = 10) {
  return request.get('/dashboard/rankings/questions', { params: { top_n: topN } })
}

/** 最常访问项目知识单元 TOP 榜 */
export function getUnitRankings(topN = 10) {
  return request.get('/dashboard/rankings/units', { params: { top_n: topN } })
}

/** Token 消耗与响应时间趋势 */
export function getTokenStats() {
  return request.get('/dashboard/stats/tokens')
}
