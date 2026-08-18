<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">数据看板</h2>
    </div>

    <!-- render_metric_cards：指标卡 -->
    <section class="metrics">
      <div v-for="card in metricCards" :key="card.label" class="metric-card">
        <span class="metric-label">{{ card.label }}</span>
        <strong class="metric-value">{{ card.value }}</strong>
      </div>
    </section>

    <div class="dashboard-grid">
      <!-- render_project_pipeline：项目阶段漏斗 -->
      <section class="card">
        <h3 class="card-title">项目阶段漏斗</h3>
        <ul class="bars">
          <li v-for="s in pipeline" :key="s.deal_stage" class="bar-row">
            <span class="bar-label">{{ s.deal_stage }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: barWidth(s.count) }"></div>
            </div>
            <span class="bar-value">{{ s.count }}</span>
          </li>
        </ul>
        <p class="summary-line">融资金额（折算 CNY）：<strong>{{ financingAmount }}</strong></p>
        <h4 class="sub-title">行业分布</h4>
        <ul class="bars">
          <li v-for="i in industry" :key="i.industry" class="bar-row">
            <span class="bar-label">{{ i.industry }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: barWidth(i.count) }"></div>
            </div>
            <span class="bar-value">{{ i.count }}</span>
          </li>
        </ul>
      </section>

      <!-- render_ranking：高频问题与常访问单元 TOP 榜 -->
      <section class="card">
        <h3 class="card-title">常见问题 TOP</h3>
        <ol class="rank-list">
          <li v-for="(q, idx) in questionRankings" :key="q.question" class="rank-item">
            <span class="rank-no" :class="{ top: idx < 3 }">{{ idx + 1 }}</span>
            <span class="rank-text">{{ q.question }}</span>
            <span class="tag">{{ q.count }}</span>
          </li>
        </ol>
        <h4 class="sub-title">常访问单元 TOP</h4>
        <ol class="rank-list">
          <li v-for="(u, idx) in unitRankings" :key="u.unit_id" class="rank-item">
            <span class="rank-no" :class="{ top: idx < 3 }">{{ idx + 1 }}</span>
            <span class="rank-text">unit#{{ u.unit_id }}</span>
            <span class="tag">{{ u.count }}</span>
          </li>
        </ol>
      </section>
    </div>

    <!-- render_trend_charts：Token 消耗/响应时间/FAQ 命中率 -->
    <section class="card">
      <h3 class="card-title">Token 消耗与响应时间趋势（近 7 天）</h3>
      <div class="trend-head">
        <span>日期</span>
        <span>Tokens</span>
        <span>平均响应(ms)</span>
      </div>
      <ul class="trend-list">
        <li v-for="t in tokenTrend" :key="t.date" class="trend-row">
          <span>{{ t.date }}</span>
          <span>{{ t.total_tokens }}</span>
          <span>{{ t.avg_response_time }}</span>
        </li>
      </ul>
      <p class="summary-line">FAQ 命中率：<strong>{{ faqHitRate }}</strong></p>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getMetrics, getProjectPipeline, getQuestionRankings, getUnitRankings, getTokenStats } from '../../api/dashboard'

const metricCards = ref([])
const pipeline = ref([])
const financingAmount = ref(0)
const industry = ref([])
const questionRankings = ref([])
const unitRankings = ref([])
const tokenTrend = ref([])
const faqHitRate = ref(0)

// render_bar_width：计算横向条形占比（纯展示）
function barWidth(value) {
  const max = Math.max(...pipeline.value.map((s) => s.count), ...industry.value.map((i) => i.count), 1)
  return `${Math.max(4, Math.round((Number(value) / max) * 100))}%`
}

async function render_metric_cards() {
  const data = await getMetrics()
  metricCards.value = [
    { label: '项目数量', value: data.project_count },
    { label: '知识单元数', value: data.knowledge_units_total },
    { label: 'Token 总量', value: data.token_total },
    { label: '平均响应时间(ms)', value: data.avg_response_time },
    { label: '访问次数', value: data.access_count },
  ]
}

async function render_project_pipeline() {
  const data = await getProjectPipeline()
  pipeline.value = data.pipeline_by_stage
  financingAmount.value = data.financing_amount.total_cny
  industry.value = data.industry_distribution
}

async function render_ranking() {
  questionRankings.value = await getQuestionRankings(10)
  unitRankings.value = await getUnitRankings(10)
}

async function render_trend_charts() {
  const data = await getTokenStats()
  tokenTrend.value = data.token_trend
  faqHitRate.value = data.faq_hit_rate
}

onMounted(() => {
  render_metric_cards()
  render_project_pipeline()
  render_ranking()
  render_trend_charts()
})
</script>

<style scoped>
.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--space-4);
}

.metric-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.metric-label {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.metric-value {
  color: var(--color-text);
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: var(--space-4);
}

.dashboard-grid .card {
  margin-top: 0;
}

.sub-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
  margin: var(--space-4) 0 var(--space-2);
}

.bars {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.bar-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.bar-label {
  width: 84px;
  flex-shrink: 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-track {
  flex: 1;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--color-bg-hover);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  transition: width var(--transition-base);
}

.bar-value {
  width: 40px;
  flex-shrink: 0;
  text-align: right;
  font-size: var(--font-size-sm);
  color: var(--color-text);
}

.summary-line {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  margin-top: var(--space-2);
}

.summary-line strong {
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}

.rank-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.rank-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.rank-no {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: var(--color-bg-hover);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
}

.rank-no.top {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.rank-text {
  flex: 1;
  min-width: 0;
  font-size: var(--font-size-sm);
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trend-head {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-subtle);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-muted);
}

.trend-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
  color: var(--color-text);
}

.trend-row:last-child {
  border-bottom: none;
}
</style>
