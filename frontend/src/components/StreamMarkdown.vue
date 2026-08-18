<template>
  <!-- render_stream_markdown：渲染流式 Markdown 回复 -->
  <div class="markdown-body">
    <span v-html="rendered" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps({
  content: { type: String, default: '' },
})

const md = new MarkdownIt()

const rendered = computed(() => md.render(props.content))
</script>
