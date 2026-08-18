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
              <td>{{ u.department_id }}</td>
              <td>{{ (u.roles || []).join('、') }}</td>
              <td><span class="badge" :class="u.status === 1 ? 'badge-success' : 'badge-muted'">{{ u.status === 1 ? '启用' : '停用' }}</span></td>
              <td>
                <div class="row-actions">
                  <button class="btn btn-ghost btn-sm" @click="editUser(u)">编辑</button>
                  <button class="btn btn-outline btn-sm" @click="onResetPassword(u)">重置密码</button>
                  <button class="btn btn-outline btn-sm" @click="onToggleStatus(u)">{{ u.status === 1 ? '停用' : '启用' }}</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listUsers, createUser, updateUser, resetPassword, setUserStatus } from '../../api/org'

const users = ref([])

async function render_user_table() {
  users.value = await listUsers()
}

async function openCreate() {
  const username = prompt('登录名')
  if (!username) return
  const password = prompt('初始密码')
  if (!password) return
  const display_name = prompt('姓名')
  if (!display_name) return
  await createUser({ username, password, display_name })
  render_user_table()
}

async function editUser(u) {
  const display_name = prompt('姓名', u.display_name)
  if (!display_name) return
  await updateUser(u.id, { display_name })
  render_user_table()
}

async function onResetPassword(u) {
  const new_password = prompt('新密码')
  if (!new_password) return
  await resetPassword(u.id, { new_password })
}

async function onToggleStatus(u) {
  await setUserStatus(u.id, { enable: u.status !== 1 })
  render_user_table()
}

onMounted(render_user_table)
</script>

<style scoped>
.row-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
