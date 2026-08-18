import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../store'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/index.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('../layout/index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/dashboard/index.vue'),
        meta: { title: '数据看板', permission: 'dashboard:view' },
      },
      {
        path: 'knowledge/import',
        name: 'KnowledgeImport',
        component: () => import('../views/knowledge/ImportView.vue'),
        meta: { title: '项目文档导入', permission: 'knowledge:import' },
      },
      {
        path: 'knowledge/units',
        name: 'KnowledgeUnits',
        component: () => import('../views/knowledge/UnitListView.vue'),
        meta: { title: '知识单元', permission: 'knowledge:view' },
      },
      {
        path: 'knowledge/units/:id/edit',
        name: 'KnowledgeUnitEdit',
        component: () => import('../views/knowledge/UnitEditView.vue'),
        meta: { title: '编辑知识单元', permission: 'knowledge:manage' },
      },
      {
        path: 'org/departments',
        name: 'OrgDepartments',
        component: () => import('../views/org/DepartmentView.vue'),
        meta: { title: '团队/基金/项目范围', permission: 'org:dept:manage' },
      },
      {
        path: 'org/users',
        name: 'OrgUsers',
        component: () => import('../views/org/UserView.vue'),
        meta: { title: '内部员工', permission: 'org:user:manage' },
      },
      {
        path: 'org/roles',
        name: 'OrgRoles',
        component: () => import('../views/org/RoleView.vue'),
        meta: { title: '角色权限', permission: 'org:role:manage' },
      },
      {
        path: 'org/profile',
        name: 'OrgProfile',
        component: () => import('../views/org/ProfileView.vue'),
        meta: { title: '个人中心' },
      },
      {
        path: 'ai/chat',
        name: 'AiChat',
        component: () => import('../views/ai/ChatView.vue'),
        meta: { title: '投融资智能问答', permission: 'qa:chat' },
      },
      {
        path: 'settlement/faqs',
        name: 'SettlementFaqs',
        component: () => import('../views/settlement/FaqReviewView.vue'),
        meta: { title: 'FAQ 审核', permission: 'settlement:faq:review' },
      },
      {
        path: 'settlement/gaps',
        name: 'SettlementGaps',
        component: () => import('../views/settlement/GapListView.vue'),
        meta: { title: '知识缺口', permission: 'settlement:gap:view' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const userStore = useUserStore()
  if (to.meta.public) return true
  if (!userStore.accessToken) return { path: '/login' }
  if (to.meta.permission && !userStore.hasPermission(to.meta.permission)) {
    // 回退到无权限要求的个人中心，而非 /dashboard（避免无 dashboard:view 权限时死循环）
    return { path: '/org/profile' }
  }
  return true
})

export default router