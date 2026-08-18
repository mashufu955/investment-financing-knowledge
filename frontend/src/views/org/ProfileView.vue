<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">个人中心</h2>
    </div>

    <!-- render_personal_center：展示当前用户身份、所属团队、基金/项目范围与拥有角色 -->
    <div class="card profile-card">
      <div class="avatar">{{ (user?.display_name || 'U').slice(0, 1) }}</div>
      <div class="profile-info">
        <p class="profile-name">{{ user?.display_name }}</p>
        <p class="profile-meta">登录名：{{ user?.username }}</p>
        <p class="profile-meta">团队：{{ user?.department_id }}</p>
        <p class="profile-meta">角色：{{ (user?.roles || []).join('、') }}</p>
        <p class="profile-meta">权限：{{ (user?.permissions || []).join('、') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useUserStore } from '../../store'
import { getMe } from '../../api/auth'

const userStore = useUserStore()
const user = ref(userStore.userInfo)

onMounted(async () => {
  user.value = await getMe()
  userStore.setSession({ access_token: userStore.accessToken, user_info: user.value, permissions: user.value.permissions })
})
</script>

<style scoped>
.profile-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-5);
  max-width: 560px;
}

.avatar {
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-hover));
  color: var(--color-surface);
  font-size: 28px;
  font-weight: var(--font-weight-semibold);
}

.profile-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.profile-name {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
}

.profile-meta {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}
</style>
