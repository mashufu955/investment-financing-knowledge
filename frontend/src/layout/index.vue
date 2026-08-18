<template>
  <div class="layout">
    <!-- render_dynamic_menus：根据权限渲染动态菜单（聊天页沉浸模式时隐藏） -->
    <aside v-if="!isChat" class="sidebar">
      <div class="sidebar-head">
        <span class="sidebar-logo">◆</span>
        <span class="sidebar-title">投融资知识库</span>
      </div>
      <nav class="menu">
        <router-link v-for="m in menus" :key="m.path" :to="m.path" class="menu-item">
          <span class="menu-icon">{{ menuIcons[m.path] }}</span>
          <span>{{ m.title }}</span>
        </router-link>
      </nav>
      <div class="sidebar-foot">
        <!-- render_personal_center：当前用户身份/团队/角色 -->
        <router-link to="/org/profile" class="user-row">
          <span class="user-avatar">{{ (currentUser?.display_name || '未')[0] }}</span>
          <span class="user-name">{{ currentUser?.display_name || '未登录' }}</span>
        </router-link>
        <button class="btn-logout" @click="logout">退出登录</button>
      </div>
    </aside>

    <main class="content" :class="{ 'chat-mode': isChat }">
      <header v-if="!isChat" class="topbar">
        <span class="topbar-title">{{ currentTitle }}</span>
        <router-link to="/org/profile" class="topbar-user">{{ currentUser?.display_name || '未登录' }}</router-link>
      </header>
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../store'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const currentTitle = computed(() => route.meta.title || '')

// render_chat_mode：聊天页沉浸模式（隐藏模块侧边栏与顶栏，ChatView 自渲染会话侧边栏）
const isChat = computed(() => route.path === '/ai/chat')

// render_dynamic_menus：根据 userStore.permissions 过滤可访问菜单
const menus = computed(() => {
  const all = [
    { path: '/dashboard', title: '数据看板', permission: 'dashboard:view' },
    { path: '/knowledge/import', title: '项目文档导入', permission: 'knowledge:import' },
    { path: '/knowledge/units', title: '知识单元', permission: 'knowledge:view' },
    { path: '/org/departments', title: '团队/基金/项目范围', permission: 'org:dept:manage' },
    { path: '/org/users', title: '内部员工', permission: 'org:user:manage' },
    { path: '/org/roles', title: '角色权限', permission: 'org:role:manage' },
    { path: '/ai/chat', title: '投融资智能问答', permission: 'qa:chat' },
    { path: '/settlement/faqs', title: 'FAQ 审核', permission: 'settlement:faq:review' },
    { path: '/settlement/gaps', title: '知识缺口', permission: 'settlement:gap:view' },
  ]
  return all.filter((m) => !m.permission || userStore.hasPermission(m.permission))
})

// render_menu_icons：菜单图标映射
const menuIcons = {
  '/dashboard': '📊',
  '/knowledge/import': '📥',
  '/knowledge/units': '🧠',
  '/org/departments': '🏢',
  '/org/users': '👥',
  '/org/roles': '🔐',
  '/ai/chat': '💬',
  '/settlement/faqs': '✔️',
  '/settlement/gaps': '🔍',
}

const currentUser = computed(() => userStore.userInfo)

function logout() {
  userStore.clearSession()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ---------- 深色侧边栏 ---------- */
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-sidebar);
  color: var(--color-sidebar-text);
}

.sidebar-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
}

.sidebar-logo {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: var(--color-primary-contrast);
  font-size: var(--font-size-xs);
}

.sidebar-title {
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-md);
}

.menu {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 10px var(--space-4);
  margin: 2px 0;
  border-radius: var(--radius-md);
  color: var(--color-sidebar-text-muted);
  font-size: var(--font-size-base);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.menu-item:hover {
  background: var(--color-sidebar-hover);
  color: var(--color-sidebar-text);
}

.menu-item.router-link-active {
  background: var(--color-sidebar-active);
  color: var(--color-sidebar-text);
}

.menu-icon {
  width: 18px;
  flex-shrink: 0;
  text-align: center;
  font-size: var(--font-size-base);
}

.sidebar-foot {
  margin-top: auto;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.user-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--color-sidebar-text);
}

.user-row:hover {
  background: var(--color-sidebar-hover);
}

.user-avatar {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: var(--color-primary-contrast);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}

.user-name {
  font-size: var(--font-size-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-logout {
  border: none;
  background: transparent;
  color: var(--color-sidebar-text-muted);
  font-size: var(--font-size-sm);
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.btn-logout:hover {
  color: var(--color-sidebar-text);
  background: var(--color-sidebar-hover);
}

/* ---------- 主内容区 ---------- */
.content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: var(--space-6);
  overflow-y: auto;
  background: var(--color-bg);
}

.content.chat-mode {
  padding: 0;
  overflow: hidden;
}

.topbar {
  height: var(--topbar-height);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  margin: calc(-1 * var(--space-6)) calc(-1 * var(--space-6)) var(--space-6);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.topbar-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
}

.topbar-user {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.topbar-user:hover {
  color: var(--color-primary);
}
</style>
