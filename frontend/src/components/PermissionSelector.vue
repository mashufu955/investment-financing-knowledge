<template>
  <!-- select_permission_entities：通用多选实体列表 -->
  <div class="checkbox-group">
    <label v-for="item in items" :key="item.id" class="checkbox-item">
      <input type="checkbox" :value="item.id" v-model="selected" />
      {{ item.name || item.display_name || item.role_name }}
    </label>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const selected = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
</script>
