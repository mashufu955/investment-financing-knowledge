<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">内部员工</h2>
      <button class="btn btn-primary" @click="openCreate">新增员工</button>
    </div>

    <!-- render_user_table：员工列表、团队归属、角色关联，支持新增、编辑、重置密码、启停用 -->
    <div class="card">
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr><th>姓名</th><th>登录名</th><th>团队</th><th>角色</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.display_name }}</td>
              <td>{{ u.username }}</td>
              <td>{{ deptName(u.department_id) }}</td>
              <td>{{ (u.roles || []).map(roleName).filter(Boolean).join('、') || '—' }}</td>
              <td><span class="badge" :class="u.status === 1 ? 'badge-success' : 'badge-muted'">{{ u.status === 1 ? '启用' : '停用' }}</span></td>
              <td>
                <div class="row-actions">
                  <button class="btn btn-ghost btn-sm" @click="openEdit(u)">编辑</button>
                  <button class="btn btn-outline btn-sm" @click="onResetPassword(u)">重置密码</button>
                  <button class="btn btn-outline btn-sm" @click="onToggleStatus(u)">{{ u.status === 1 ? '停用' : '启用' }}</button>
                  <button class="btn btn-danger btn-sm" @click="onDeleteUser(u)" :disabled="u.id === currentUserId">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ====== 新增/编辑员工弹窗 ====== -->
    <div v-if="showEdit" class="modal-mask" @click.self="showEdit = false">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title">{{ editingUser ? '编辑员工' : '新增员工' }}</span>
          <button class="modal-close" @click="showEdit = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="edit-form">
            <div class="field">
              <label class="field-label">登录名</label>
              <input v-model="editForm.username" class="input" :disabled="!!editingUser" placeholder="登录账号（唯一）" />
            </div>
            <div v-if="!editingUser" class="field">
              <label class="field-label">初始密码</label>
              <input v-model="editForm.password" type="password" class="input" placeholder="初始登录密码" />
            </div>
            <div class="field">
              <label class="field-label">姓名</label>
              <input v-model="editForm.display_name" class="input" placeholder="员工姓名" />
            </div>
            <div class="field">
              <label class="field-label">团队 / 基金 / 项目范围</label>
              <select v-model="editForm.department_id" class="select">
                <option :value="null">— 不指定 —</option>
                <option v-for="d in flatDepts" :key="d.id" :value="d.id">
                  {{ '　'.repeat(d._depth) }}{{ d.name }}
                </option>
              </select>
            </div>
            <div class="field">
              <label class="field-label">角色</label>
              <div class="checkbox-group">
                <label v-for="r in roles" :key="r.id" class="checkbox-item">
                  <input type="checkbox" :value="r.id" v-model="editForm.role_ids" />
                  <span>{{ r.role_name }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" :disabled="saving || !editForm.username || !editForm.display_name || (!editingUser && !editForm.password)" @click="saveEdit">
            {{ saving ? '保存中…' : '保存' }}
          </button>
          <button class="btn btn-ghost" @click="showEdit = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '../../store'
import { listUsers, createUser, updateUser, deleteUser, resetPassword, setUserStatus, listDepartments, listRoles } from '../../api/org'

const userStore = useUserStore()
const users = ref([])
const departments = ref([])   // 树形
const flatDepts = ref([])     // 扁平化（带 _depth 缩进）
const roles = ref([])

// 当前登录用户 id（用于禁用删除自己）
const currentUserId = ref(userStore.userInfo?.id ?? null)

// 弹窗状态
const showEdit = ref(false)
const editingUser = ref(null) // null=新增 对象=编辑
const editForm = ref({ username: '', password: '', display_name: '', department_id: null, role_ids: [] })
const saving = ref(false)

// 部门树扁平化（缩进展示层级）
function flattenDepts(nodes, depth = 0) {
  const result = []
  for (const n of nodes || []) {
    result.push({ ...n, _depth: depth })
    if (n.children && n.children.length) result.push(...flattenDepts(n.children, depth + 1))
  }
  return result
}

function deptName(id) {
  if (!id) return '—'
  return flatDepts.value.find((d) => d.id === id)?.name || `#${id}`
}

function roleName(code) {
  return roles.value.find((r) => r.role_code === code)?.role_name || code
}

async function render_user_table() {
  users.value = await listUsers()
}

async function loadOptions() {
  const [deptRes, roleRes] = await Promise.all([listDepartments(), listRoles()])
  departments.value = deptRes || []
  flatDepts.value = flattenDepts(departments.value)
  roles.value = roleRes || []
}

function openCreate() {
  editingUser.value = null
  editForm.value = { username: '', password: '', display_name: '', department_id: null, role_ids: [] }
  showEdit.value = true
}

function openEdit(u) {
  editingUser.value = u
  editForm.value = {
    username: u.username,
    password: '',
    display_name: u.display_name,
    department_id: u.department_id ?? null,
    // list_users 返回的 roles 是 role_code 数组，映射回 role_id 用于回显勾选
    role_ids: roles.value.filter((r) => (u.roles || []).includes(r.role_code)).map((r) => r.id),
  }
  showEdit.value = true
}

async function saveEdit() {
  if (!editForm.value.username.trim() || !editForm.value.display_name.trim()) return
  if (!editingUser.value && !editForm.value.password.trim()) return
  saving.value = true
  try {
    if (editingUser.value) {
      await updateUser(editingUser.value.id, {
        display_name: editForm.value.display_name.trim(),
        department_id: editForm.value.department_id,
        role_ids: editForm.value.role_ids,
      })
    } else {
      await createUser({
        username: editForm.value.username.trim(),
        password: editForm.value.password.trim(),
        display_name: editForm.value.display_name.trim(),
        department_id: editForm.value.department_id,
        role_ids: editForm.value.role_ids,
      })
    }
    showEdit.value = false
    await render_user_table()
  } finally {
    saving.value = false
  }
}

async function onResetPassword(u) {
  const new_password = prompt(`为「${u.display_name}」设置新密码`)
  if (!new_password) return
  await resetPassword(u.id, { new_password })
}

async function onToggleStatus(u) {
  await setUserStatus(u.id, { enable: u.status !== 1 })
  await render_user_table()
}

async function onDeleteUser(u) {
  if (!confirm(`确认删除员工「${u.display_name}」（${u.username}）吗？\n将同步清理其角色关联，此操作不可恢复。`)) return
  await deleteUser(u.id)
  await render_user_table()
}

onMounted(async () => {
  await loadOptions()
  await render_user_table()
})
</script>

<style scoped>
.row-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}
.checkbox-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
</style>
