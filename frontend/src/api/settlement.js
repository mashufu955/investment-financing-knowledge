import request from './request'

/** 高频问题挖掘推荐列表 */
export function listFaqRecommendations() {
  return request.get('/settlement/faqs/recommendations')
}

/** 审核 FAQ */
export function reviewFaq(id, data) {
  return request.post(`/settlement/faqs/${id}/review`, data)
}

/** 已发布 FAQ 库及缓存生效状态 */
export function listPublishedFaqs() {
  return request.get('/settlement/faqs')
}

/** 知识缺口列表 */
export function listKnowledgeGaps() {
  return request.get('/settlement/knowledge-gaps')
}

/** 一键创建关联投融资知识单元以补全缺口 */
export function createUnitFromGap(data) {
  return request.post('/knowledge/units', data)
}
