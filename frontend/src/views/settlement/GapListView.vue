<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">知识缺口</h2>
    </div>

    <!-- render_gap_list：知识缺口列表、提问频次、最近提问时间 -->
    <div class="card">
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr><th>问题模式</th><th>提问频次</th><th>最近提问</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="g in gaps" :key="g.id">
              <td>{{ g.question_pattern }}</td>
              <td>{{ g.ask_count }}</td>
              <td>{{ g.last_asked_at }}</td>
              <td><span class="badge badge-warning">{{ g.status }}</span></td>
              <td>
                <!-- create_unit_from_gap：一键创建关联投融资知识单元以补全缺口 -->
                <button class="btn btn-outline btn-sm" @click="create_unit_from_gap(g)">一键创建知识单元</button>
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
import { useRouter } from 'vue-router'
import { listKnowledgeGaps } from '../../api/settlement'

const gaps = ref([])
const router = useRouter()

async function render_gap_list() {
  gaps.value = await listKnowledgeGaps()
}

async function create_unit_from_gap(gap) {
  const title = prompt('为该缺口输入知识单元标题', gap.question_pattern)
  if (!title) return
  const { createUnitFromGap } = await import('../../api/settlement')
  await createUnitFromGap({ gap_id: gap.id, title })
  // 创建后刷新缺口列表（后端已通过 gap_id 自动标记缺口为 resolved）
  await render_gap_list()
}

onMounted(render_gap_list)
</script>
