<template>
  <!-- render_reference_card：渲染投融资知识引用来源卡片 -->
  <div class="reference-card">
    <div class="reference-card__title">引用来源</div>
    <ul class="reference-card__list">
      <li v-for="s in sources" :key="s.id" class="reference-card__item">
        {{ s.title }}
        <span v-if="s.unit_code" class="tag">{{ s.unit_code }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  sources: { type: Array, default: () => [] },
})
</script>
