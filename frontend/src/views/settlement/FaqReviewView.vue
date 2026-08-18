<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">FAQ 审核</h2>
    </div>

    <!-- render_faq_recommendations：推荐列表、推荐频次、关联知识单元、建议答案，提供审核通过与驳回操作 -->
    <div class="card">
      <h3 class="card-title">待审核推荐</h3>
      <div v-for="f in recommendations" :key="f.id" class="review-card">
        <div class="review-head">
          <strong class="review-question">{{ f.question }}</strong>
          <span class="tag">频次：{{ f.hit_count }}</span>
        </div>
        <p class="review-meta">关联单元：{{ f.related_unit_id }}｜建议答案：{{ f.answer }}</p>
        <div class="review-actions">
          <button class="btn btn-primary btn-sm" @click="onReview(f, 'approve')">通过</button>
          <button class="btn btn-outline btn-sm" @click="onReview(f, 'reject')">驳回</button>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 class="card-title">已发布 FAQ</h3>
      <ul v-if="published.length" class="published-list">
        <li v-for="p in published" :key="p.id" class="published-item">
          <span>{{ p.question }}</span>
          <span class="tag" :class="p.cache_status === 'active' ? 'badge-success' : 'badge-muted'">{{ p.cache_status }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listFaqRecommendations, reviewFaq, listPublishedFaqs } from '../../api/settlement'

const recommendations = ref([])
const published = ref([])

async function render_faq_recommendations() {
  recommendations.value = await listFaqRecommendations()
}

async function loadPublished() {
  published.value = await listPublishedFaqs()
}

async function onReview(faq, action) {
  await reviewFaq(faq.id, { action })
  render_faq_recommendations()
  loadPublished()
}

onMounted(() => {
  render_faq_recommendations()
  loadPublished()
})
</script>

<style scoped>
.review-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--color-border);
}

.review-card:last-child {
  border-bottom: none;
}

.review-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.review-question {
  color: var(--color-text);
  font-size: var(--font-size-base);
}

.review-meta {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.review-actions {
  display: flex;
  gap: var(--space-2);
}

.published-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.published-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-subtle);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: var(--font-size-sm);
}
</style>
