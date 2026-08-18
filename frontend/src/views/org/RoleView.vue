<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">角色权限</h2>
      <button class="btn btn-primary" @click="openCreate">新增角色</button>
    </div>

    <!-- render_role_permission_tree：角色卡片平铺布局，含名称、编码、描述、当前权限与操作 -->
    <div class="role-grid">
      <div v-for="r in roles" :key="r.id" class="card role-card">
        <div class="role-head">
          <span class="role-name">{{ r.role_name }}</span>
          <span class="tag">{{ r.role_code }}</span>
        </div>
        <p v-if="r.description" class="role-desc">{{ r.description }}</p>

        <div class="perm-summary">
          <span class="perm-count">权限 {{ (r.permissions || []).length }} 项</span>
          <div v-if="(r.permissions || []).length" class="perm-chips">
            <span v-for="code in r.permissions" :key="code" class="perm-chip">{{ permLabel(code) }}</span>
          </div>
          <span v-else class="perm-empty">未分配权限</span>
        </div>

        <div class="role-actions">
          <button class="btn btn-outline btn-sm" @click="openPermissionTree(r)">调整权限</button>
          <button class="btn btn-ghost btn-sm" @click="onUpdate(r)">编辑</button>
          <button class="btn btn-danger btn-sm" @click="onDelete(r)">删除</button>
        </div>
      </div>
    </div>

    <!-- open_permission_dialog：调整权限弹窗，可选项勾选操作权限后保存 -->
    <div v-if="showPermDialog" class="modal-mask" @click.self="closePermissionDialog">
      <div class="modal">
        <div class="modal-header">
          <h3 class="modal-title">调整权限 —— {{ currentRole?.role_name }}</h3>
          <button class="modal-close" @click="closePermissionDialog">×</button>
        </div>

        <div class="modal-body">
          <div class="perm-toolbar">
            <span class="perm-hint">已选 {{ pickedPermissions.length }} / {{ PERMISSION_OPTIONS.length }}</span>
            <div class="perm-toolbar-actions">
              <button class="btn btn-ghost btn-sm" @click="toggleAllPermissions(true)">全选</button>
              <button class="btn btn-ghost btn-sm" @click="toggleAllPermissions(false)">清空</button>
            </div>
          </div>
          <!-- select_permission_entities：逐项勾选操作权限（可选） -->
          <label v-for="p in PERMISSION_OPTIONS" :key="p.code" class="checkbox-item perm-item">
            <input type="checkbox" :value="p.code" v-model="pickedPermissions" />
            <span class="perm-label">{{ p.label }}</span>
            <code class="perm-code">{{ p.code }}</code>
          </label>
        </div>

        <div class="modal-footer">
          <button class="btn btn-outline" @click="closePermissionDialog">取消</button>
          <button class="btn btn-primary" :disabled="saving" @click="savePermissions">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listRoles, createRole, updateRole, deleteRole, assignRolePermissions } from '../../api/org'

const roles = ref([])

// 权限可选项（code → 中文名称），供弹窗复选与卡片标签复用
const PERMISSION_OPTIONS = [
  { code: 'org:user:manage', label: '用户管理' },
  { code: 'org:role:manage', label: '角色管理' },
  { code: 'org:dept:manage', label: '团队管理' },
  { code: 'knowledge:import', label: '知识导入' },
  { code: 'knowledge:manage', label: '知识管理' },
  { code: 'knowledge:view', label: '知识查看' },
  { code: 'qa:chat', label: '智能问答' },
  { code: 'dashboard:view', label: '看板查看' },
  { code: 'settlement:faq:review', label: 'FAQ复核' },
  { code: 'settlement:gap:view', label: '缺口查看' },
]

const ALL_PERMISSIONS = PERMISSION_OPTIONS.map((p) => p.code)

function permLabel(code) {
  return PERMISSION_OPTIONS.find((p) => p.code === code)?.label || code
}

// 弹窗状态
const showPermDialog = ref(false)
const currentRole = ref(null)
const pickedPermissions = ref([])
const saving = ref(false)

async function render_role_permission_tree() {
  roles.value = await listRoles()
}

async function openCreate() {
  const role_name = prompt('角色名称')
  if (!role_name) return
  const role_code = prompt('角色编码')
  if (!role_code) return
  await createRole({ role_name, role_code })
  render_role_permission_tree()
}

function openPermissionTree(r) {
  // 打开调整权限弹窗，预选当前已有权限（可选可调）
  currentRole.value = r
  pickedPermissions.value = [...(r.permissions || [])]
  showPermDialog.value = true
}

function closePermissionDialog() {
  showPermDialog.value = false
  currentRole.value = null
  pickedPermissions.value = []
}

function toggleAllPermissions(checked) {
  pickedPermissions.value = checked ? [...ALL_PERMISSIONS] : []
}

async function savePermissions() {
  if (!currentRole.value) return
  saving.value = true
  try {
    await assignRolePermissions(currentRole.value.id, pickedPermissions.value)
    closePermissionDialog()
    await render_role_permission_tree()
  } finally {
    saving.value = false
  }
}

async function onUpdate(r) {
  const role_name = prompt('角色名称', r.role_name)
  if (!role_name) return
  await updateRole(r.id, { role_name, role_code: r.role_code })
  render_role_permission_tree()
}

async function onDelete(r) {
  if (!confirm(`确认删除角色 ${r.role_name} 吗？`)) return
  await deleteRole(r.id)
  render_role_permission_tree()
}

onMounted(render_role_permission_tree)
</script>

<style scoped>
.role-grid {
  display: grid;
  /* 每行固定 3 张卡片，等宽铺满 */
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  align-items: stretch;
}

@media (max-width: 900px) {
  .role-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .role-grid {
    grid-template-columns: 1fr;
  }
}

.role-card {
  margin-top: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.role-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.role-name {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
}

.role-desc {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}

.perm-summary {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

.perm-count {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.perm-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.perm-chip {
  display: inline-block;
  padding: 2px 8px;
  font-size: var(--font-size-xs);
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
  border-radius: 4px;
}

.perm-empty {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.role-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: auto;
}

.perm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.perm-hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.perm-toolbar-actions {
  display: flex;
  gap: var(--space-2);
}
</style>
