<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">团队 / 基金 / 项目范围</h2>
      <button class="btn btn-primary" @click="openCreate(null)">新增顶级团队</button>
    </div>

    <!-- 顶部统计 -->
    <div class="dept-stats">
      <div class="stat-card">
        <span class="stat-value">{{ totalNodes }}</span>
        <span class="stat-label">节点总数</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ tree.length }}</span>
        <span class="stat-label">顶级团队</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ maxDepth }}</span>
        <span class="stat-label">最大层级</span>
      </div>
    </div>

    <!-- 团队卡片网格（仅顶级节点） -->
    <div v-if="tree.length" class="team-grid">
      <div v-for="d in tree" :key="d.id" class="team-card">
        <div class="card-accent" :style="{ background: typeMeta(d).color }"></div>
        <div class="card-body">
          <div class="card-head">
            <span class="type-badge" :style="typeBadgeStyle(d)">{{ typeMeta(d).label }}</span>
            <span class="team-name">{{ d.name }}</span>
          </div>
          <div class="card-meta">
            <span class="meta-item">
              <span class="meta-label">负责人</span>
              <span class="meta-value">{{ d.leader_name || '未指定' }}</span>
            </span>
            <span class="meta-sep">·</span>
            <span class="meta-item">
              <span class="meta-label">成员</span>
              <span class="meta-value">{{ d.member_count ?? 0 }} 人</span>
            </span>
            <span class="meta-sep">·</span>
            <span class="meta-item">
              <span class="meta-label">子节点</span>
              <span class="meta-value">{{ (d.children || []).length }}</span>
            </span>
          </div>
          <div class="card-actions">
            <button class="btn btn-outline btn-sm" @click="openChildren(d)" :disabled="!(d.children && d.children.length)">
              查看子节点
            </button>
            <button class="btn btn-ghost btn-sm" @click="openEdit(d)">编辑</button>
            <button class="btn btn-ghost btn-sm" @click="openCreate(d)">新增子节点</button>
            <button class="btn btn-danger btn-sm" @click="onDelete(d)">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <p class="empty-text">暂无团队/基金/项目节点</p>
      <button class="btn btn-primary" @click="openCreate(null)">创建第一个团队</button>
    </div>

    <!-- ====== 子节点表格弹窗 ====== -->
    <div v-if="showChildren" class="modal-mask" @click.self="showChildren = false">
      <div class="modal modal-lg">
        <div class="modal-header">
          <span class="modal-title">{{ childrenNode?.name }} — 子节点列表</span>
          <button class="modal-close" @click="showChildren = false">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="flatChildren.length" class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>分类</th>
                  <th>负责人</th>
                  <th>成员</th>
                  <th>层级</th>
                  <th class="col-actions">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in flatChildren" :key="row.id">
                  <td>{{ '　'.repeat(row._depth - 1) }}{{ row.name }}</td>
                  <td><span class="type-badge-sm" :style="typeBadgeStyle(row)">{{ typeMeta(row).label }}</span></td>
                  <td>{{ row.leader_name || '—' }}</td>
                  <td>{{ row.member_count ?? 0 }}</td>
                  <td>L{{ row._depth }}</td>
                  <td class="col-actions">
                    <button class="btn btn-ghost btn-sm" @click="openEdit(row)">编辑</button>
                    <button class="btn btn-danger btn-sm" @click="onDelete(row)">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="empty">该节点暂无子节点</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary btn-sm" @click="openCreate(childrenNode)">新增子节点</button>
          <button class="btn btn-ghost" @click="showChildren = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- ====== 编辑/新增弹窗 ====== -->
    <div v-if="showEdit" class="modal-mask" @click.self="showEdit = false">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title">{{ editingNode ? '编辑节点' : '新增节点' }}</span>
          <button class="modal-close" @click="showEdit = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="edit-form">
            <div class="field">
              <label class="field-label">名称</label>
              <input v-model="editForm.name" class="input" placeholder="团队/基金/项目组名称" />
            </div>
            <div class="field">
              <label class="field-label">分类</label>
              <select v-model="editForm.dept_type" class="select">
                <option value="team">团队</option>
                <option value="fund">基金</option>
                <option value="project">项目</option>
                <option value="sub">子项</option>
              </select>
            </div>
            <div class="field">
              <label class="field-label">负责人</label>
              <select v-model="editForm.leader_id" class="select">
                <option :value="null">— 不指定 —</option>
                <option v-for="u in users" :key="u.id" :value="u.id">
                  {{ u.display_name }}（{{ u.username }}）
                </option>
              </select>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" :disabled="saving || !editForm.name" @click="saveEdit">
            {{ saving ? '保存中…' : '保存' }}
          </button>
          <button class="btn btn-ghost" @click="showEdit = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { listDepartments, createDepartment, updateDepartment, deleteDepartment, listUsers } from '../../api/org'

const tree = ref([])
const users = ref([])

// 弹窗状态
const showEdit = ref(false)
const editingNode = ref(null)     // null=新增  对象=编辑
const editParent = ref(null)       // 新增时的父节点
const editForm = ref({ name: '', dept_type: 'team', leader_id: null })
const saving = ref(false)

const showChildren = ref(false)
const childrenNode = ref(null)

// ===== 分类配色 =====
const TYPE_MAP = {
  team:    { label: '团队', color: '#10a37f', soft: '#e6f4f1' },
  fund:    { label: '基金', color: '#06b6d4', soft: '#e0f7fb' },
  project: { label: '项目', color: '#b7791f', soft: '#fdf3e7' },
  sub:     { label: '子项', color: '#6e6e80', soft: '#f0f0f3' },
}
function typeMeta(node) {
  return TYPE_MAP[node?.dept_type] || TYPE_MAP.sub
}
function typeBadgeStyle(node) {
  const m = typeMeta(node)
  return { background: m.soft, color: m.color }
}

// ===== 统计 =====
function countNodes(nodes) {
  return nodes.reduce((s, n) => s + 1 + countNodes(n.children || []), 0)
}
function depthOf(nodes, base = 0) {
  if (!nodes.length) return base
  return Math.max(...nodes.map((n) => depthOf(n.children || [], base + 1)))
}
const totalNodes = computed(() => countNodes(tree.value))
const maxDepth = computed(() => depthOf(tree.value))

// ===== 扁平化子节点（递归） =====
function flattenDescendants(nodes, depth = 1) {
  const result = []
  for (const n of nodes) {
    result.push({ ...n, _depth: depth })
    if (n.children && n.children.length) {
      result.push(...flattenDescendants(n.children, depth + 1))
    }
  }
  return result
}
const flatChildren = computed(() => {
  if (!childrenNode.value) return []
  return flattenDescendants(childrenNode.value.children || [])
})

// ===== 数据加载 =====
async function load() {
  const [deptRes, userRes] = await Promise.all([
    listDepartments(),
    listUsers(),
  ])
  tree.value = deptRes || []
  users.value = userRes || []
}

// ===== 弹窗操作 =====
function openCreate(parent) {
  editingNode.value = null
  editParent.value = parent
  // 根据父节点自动推断子节点分类
  const inferred = parent
    ? { team: 'fund', fund: 'project', project: 'sub', sub: 'sub' }[parent.dept_type || 'team'] || 'sub'
    : 'team'
  editForm.value = { name: '', dept_type: inferred, leader_id: null }
  showEdit.value = true
}

function openEdit(node) {
  editingNode.value = node
  editParent.value = null
  editForm.value = {
    name: node.name,
    dept_type: node.dept_type || 'sub',
    leader_id: node.leader_id ?? null,
  }
  showEdit.value = true
}

async function saveEdit() {
  if (!editForm.value.name.trim()) return
  saving.value = true
  try {
    if (editingNode.value) {
      await updateDepartment(editingNode.value.id, {
        name: editForm.value.name.trim(),
        dept_type: editForm.value.dept_type,
        leader_id: editForm.value.leader_id,
      })
    } else {
      await createDepartment({
        name: editForm.value.name.trim(),
        dept_type: editForm.value.dept_type,
        leader_id: editForm.value.leader_id,
        parent_id: editParent.value?.id ?? null,
        sort_order: 0,
      })
    }
    showEdit.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function openChildren(node) {
  childrenNode.value = node
  showChildren.value = true
}

async function onDelete(node) {
  if (!confirm(`确认删除「${node.name}」吗？${(node.children || []).length ? '其下子节点将一并移除。' : ''}`)) return
  await deleteDepartment(node.id)
  showChildren.value = false
  await load()
}

onMounted(load)
</script>

<style scoped>
/* ===== 统计 ===== */
.dept-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xs);
}
.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-primary);
}
.stat-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

/* ===== 卡片网格 ===== */
.team-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  align-items: stretch;
}
.team-card {
  display: flex;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  overflow: hidden;
  transition: box-shadow var(--transition-base), transform var(--transition-base);
}
.team-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.card-accent {
  width: 4px;
  flex-shrink: 0;
}
.card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
}
.card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.type-badge {
  flex-shrink: 0;
  padding: 2px 8px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  border-radius: var(--radius-full);
}
.team-name {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.meta-item { display: inline-flex; align-items: center; gap: 4px; }
.meta-label { color: var(--color-text-muted); }
.meta-value { color: var(--color-text-secondary); font-weight: var(--font-weight-medium); }
.meta-sep { color: var(--color-text-muted); margin: 0 2px; }
.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

/* ===== 弹窗 ===== */
.modal-lg {
  width: min(820px, 95vw);
}
.col-actions {
  white-space: nowrap;
  text-align: right;
}
.type-badge-sm {
  display: inline-block;
  padding: 1px 6px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  border-radius: var(--radius-full);
}
.edit-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* ===== 空状态 ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12) 0;
  color: var(--color-text-muted);
}
.empty-text { margin: 0; font-size: var(--font-size-base); }

/* ===== 响应式 ===== */
@media (max-width: 900px) {
  .team-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .team-grid { grid-template-columns: 1fr; }
  .dept-stats { grid-template-columns: repeat(3, 1fr); }
  .stat-value { font-size: var(--font-size-lg); }
}
</style>
