<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">知识单元</h2>
    </div>

    <!-- 过滤条件：行业/轮次/项目阶段/保密级别/状态 -->
    <div class="card">
      <div class="filters">
        <input v-model="query.industry" class="input" placeholder="行业" @change="loadUnits" />
        <input v-model="query.financing_round" class="input" placeholder="轮次" @change="loadUnits" />
        <input v-model="query.deal_stage" class="input" placeholder="项目阶段" @change="loadUnits" />
        <input v-model.number="query.confidential_level" class="input" placeholder="保密级别" @change="loadUnits" />
        <select v-model="query.status" class="select" @change="loadUnits">
          <option value="">全部状态</option>
          <option value="active">active</option>
          <option value="draft">draft</option>
          <option value="archived">archived</option>
        </select>
      </div>

      <!-- render_unit_list：知识单元列表 -->
      <p v-if="loadError" class="error-text">加载知识单元失败：{{ loadError }}</p>
      <p v-else-if="!units.length" class="empty-text">暂无知识单元</p>
      <div v-if="units.length" class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>编号</th><th>标题</th><th>行业</th><th>轮次</th><th>阶段</th>
              <th>数据权限摘要</th><th>创建人</th><th>更新时间</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in units" :key="u.id">
              <td>{{ u.unit_code }}</td>
              <td>{{ u.title }}</td>
              <td>{{ u.industry }}</td>
              <td>{{ u.financing_round }}</td>
              <td>{{ u.deal_stage }}</td>
              <td>{{ u.permission_summary }}</td>
              <td>{{ u.creator_id }}</td>
              <td>{{ u.updated_at }}</td>
              <td><span class="badge" :class="statusBadge(u.status)">{{ u.status }}</span></td>
              <td>
                <div class="row-actions">
                  <router-link :to="`/knowledge/units/${u.id}/edit`" class="btn btn-ghost btn-sm">编辑</router-link>
                  <button class="btn btn-outline btn-sm" @click="openPermission(u)">数据权限</button>
                  <button class="btn btn-danger btn-sm" @click="onDelete(u)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <PermissionDialog v-if="permissionTarget" :unit="permissionTarget" @close="permissionTarget = null" />
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { listUnits, getUnit, deleteUnits } from '../../api/knowledge'
import PermissionDialog from './PermissionDialog.vue'

const units = ref([])
const permissionTarget = ref(null)
const loadError = ref('')
const query = reactive({
  industry: '',
  financing_round: '',
  deal_stage: '',
  confidential_level: '',
  status: '',
  page: 1,
  page_size: 20,
})

// 过滤空串/NaN 参数：空字符串会让后端 int | None 参数（confidential_level）校验失败返回 422
function cleanQuery(q) {
  return Object.fromEntries(
    Object.entries(q).filter(([, v]) => v !== '' && v !== null && v !== undefined && !Number.isNaN(v))
  )
}

// status_badge：状态 → 徽章类（纯展示）
function statusBadge(s) {
  return s === 'active' ? 'badge-success' : s === 'draft' ? 'badge-warning' : 'badge-muted'
}

async function render_unit_list() {
  loadError.value = ''
  try {
    const data = await listUnits(cleanQuery(query))
    units.value = data.items || []
  } catch (err) {
    units.value = []
    const detail = err?.response?.data?.detail
    loadError.value = typeof detail === 'string' ? detail : (err?.message || '请求失败')
  }
}

async function loadUnits() {
  render_unit_list()
}

function openPermission(unit) {
  permissionTarget.value = unit
}

async function onDelete(u) {
  await deleteUnits([u.id])
  render_unit_list()
}

onMounted(render_unit_list)
</script>

<style scoped>
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.filters .input,
.filters .select {
  width: 160px;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.error-text {
  color: #d92d20;
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-3);
}

.empty-text {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-3);
}
</style>
