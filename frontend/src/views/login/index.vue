<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <!-- OpenAI 风格品牌 logo -->
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L22 19H2L12 2Z" fill="white" />
        </svg>
      </div>
      <div class="login-head">
        <h1 class="login-title">投融资知识库管理平台</h1>
        <p class="login-subtitle">AI 驱动的投融资知识问答与协作</p>
      </div>
      <form class="login-form" @submit.prevent="login">
        <div class="field">
          <label class="field-label" for="username">用户名</label>
          <input id="username" class="input" v-model="form.username" placeholder="请输入用户名" autocomplete="username" />
        </div>
        <div class="field">
          <label class="field-label" for="password">密码</label>
          <input id="password" class="input" v-model="form.password" type="password" placeholder="请输入密码" autocomplete="current-password" />
        </div>
        <button type="submit" class="btn btn-primary login-btn">登 录</button>
      </form>
      <p class="login-footer">© 2026 投融资知识库管理平台</p>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../store'
import { login as loginApi } from '../../api/auth'

const router = useRouter()
const userStore = useUserStore()
const form = reactive({ username: '', password: '' })

// login：调用 POST /api/auth/login，保存会话后进入看板
async function login() {
  const data = await loginApi(form)
  userStore.setSession(data)
  router.push('/dashboard')
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
  padding: var(--space-6);
}

.login-card {
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.login-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-md);
}

.login-head {
  text-align: center;
}

.login-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
}

.login-subtitle {
  margin-top: var(--space-2);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.login-btn {
  width: 100%;
  padding: 11px 16px;
  font-size: var(--font-size-md);
}

.login-footer {
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}
</style>
