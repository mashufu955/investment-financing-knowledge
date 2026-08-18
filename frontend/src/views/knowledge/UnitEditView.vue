<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">编辑知识单元</h2>
    </div>

    <!-- edit_unit：编辑知识标题、正文内容、标签、附件及项目/融资业务字段 -->
    <div class="card">
      <form class="form-grid" @submit.prevent="save">
        <div class="field">
          <label class="field-label">标题</label>
          <input v-model="form.title" class="input" />
        </div>
        <div class="field">
          <label class="field-label">行业</label>
          <input v-model="form.industry" class="input" />
        </div>
        <div class="field">
          <label class="field-label">轮次</label>
          <input v-model="form.financing_round" class="input" />
        </div>
        <div class="field">
          <label class="field-label">金额</label>
          <input v-model.number="form.amount" class="input" />
        </div>
        <div class="field">
          <label class="field-label">币种</label>
          <input v-model="form.currency" class="input" />
        </div>
        <div class="field">
          <label class="field-label">估值</label>
          <input v-model.number="form.valuation" class="input" />
        </div>
        <div class="field">
          <label class="field-label">地区</label>
          <input v-model="form.region" class="input" />
        </div>
        <div class="field">
          <label class="field-label">项目阶段</label>
          <input v-model="form.deal_stage" class="input" />
        </div>
        <div class="field">
          <label class="field-label">保密级别</label>
          <input v-model.number="form.confidential_level" class="input" />
        </div>
        <div class="field field-full">
          <label class="field-label">正文</label>
          <textarea v-model="form.content" class="textarea" rows="10"></textarea>
        </div>
        <div class="field field-full">
          <button type="submit" class="btn btn-primary">保存</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getUnit, updateUnit } from '../../api/knowledge'

const route = useRoute()
const router = useRouter()
const unitId = route.params.id

const form = reactive({
  title: '', content: '', industry: '', financing_round: '',
  amount: null, currency: '', valuation: null, region: '', deal_stage: '',
  confidential_level: 1, status: 'active',
})

// 加载单元详情（含已配置的数据权限列表）
onMounted(async () => {
  const data = await getUnit(unitId)
  Object.assign(form, {
    title: data.title,
    content: data.content || '',
    industry: data.industry || '',
    financing_round: data.financing_round || '',
    amount: data.amount,
    currency: data.currency || '',
    valuation: data.valuation,
    region: data.region || '',
    deal_stage: data.deal_stage || '',
    confidential_level: data.confidential_level,
    status: data.status,
  })
})

// edit_unit：保存编辑后的知识标题、正文内容、标签、附件及项目/融资业务字段
async function save() {
  await updateUnit(unitId, form)
  router.push('/knowledge/units')
}
</script>
