<template>
  <!-- render_permission_missing_card：渲染无项目权限时的缺失提示卡片 -->
  <div class="permission-missing-card">
    <strong>以下内容因缺少项目数据权限未纳入回答：</strong>
    <span v-for="u in units" :key="u.id" class="tag">{{ u.title }}</span>
  </div>
</template>

<script setup>
defineProps({
  units: { type: Array, default: () => [] },
})
</script>
