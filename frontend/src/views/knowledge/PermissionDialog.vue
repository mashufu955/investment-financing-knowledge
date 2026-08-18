<template>
  <!-- open_permission_dialog：统一的数据权限选择弹窗 -->
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <h3 class="modal-title">数据权限 —— {{ unit?.title }}</h3>
        <button class="modal-close" @click="$emit('close')">×</button>
      </div>

      <div class="modal-body">
        <!-- select_permission_entities：勾选全局公开、多选团队、多选角色、多选人员 -->
        <fieldset class="fieldset">
          <legend class="fieldset-legend">全局公开</legend>
          <label class="checkbox-item">
            <input type="checkbox" v-model="form.global" />
            对所有人公开此单元
          </label>
        </fieldset>
        <fieldset class="fieldset">
          <legend class="fieldset-legend">团队 / 基金 / 项目范围</legend>
          <PermissionSelector :items="departments" v-model="form.departments" />
        </fieldset>
        <fieldset class="fieldset">
          <legend class="fieldset-legend">角色</legend>
          <PermissionSelector :items="roles" v-model="form.roles" />
        </fieldset>
        <fieldset class="fieldset">
          <legend class="fieldset-legend">人员</legend>
          <PermissionSelector :items="users" v-model="form.users" />
        </fieldset>
      </div>

      <!-- save_permissions：保存投融资数据权限配置 -->
      <div class="modal-footer">
        <button class="btn btn-outline" @click="$emit('close')">取消</button>
        <button class="btn btn-primary" @click="save_permissions">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { configureUnitPermissions, getUnit } from '../../api/knowledge'
import { listDepartments, listRoles } from '../../api/org'
import PermissionSelector from '../../components/PermissionSelector.vue'

const props = defineProps({
  unit: { type: Object, required: true },
})

const departments = ref([])
const roles = ref([])
const users = ref([])

const form = reactive({ global: false, departments: [], roles: [], users: [] })

async function open_permission_dialog() {
  const [dept, role] = await Promise.all([listDepartments(), listRoles()])
  departments.value = dept || []
  roles.value = role || []
  const detail = await getUnit(props.unit.id)
  const summary = detail.permission_summary || []
  form.global = summary.some((p) => p.target_type === 'global')
  form.departments = summary.filter((p) => p.target_type === 'department').map((p) => p.target_id)
  form.roles = summary.filter((p) => p.target_type === 'role').map((p) => p.target_id)
  form.users = summary.filter((p) => p.target_type === 'user').map((p) => p.target_id)
}

function select_permission_entities() {
  // 勾选态由 v-model 直接绑定
}

async function save_permissions() {
  const entities = []
  if (form.global) entities.push({ target_type: 'global', target_id: 0 })
  form.departments.forEach((id) => entities.push({ target_type: 'department', target_id: id }))
  form.roles.forEach((id) => entities.push({ target_type: 'role', target_id: id }))
  form.users.forEach((id) => entities.push({ target_type: 'user', target_id: id }))
  await configureUnitPermissions(props.unit.id, entities)
  emit('close')
}

const emit = defineEmits(['close'])

onMounted(open_permission_dialog)
</script>

<style scoped>
.fieldset {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-bottom: var(--space-3);
}

.fieldset-legend {
  padding: 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
}
</style>
