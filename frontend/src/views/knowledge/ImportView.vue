<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">项目文档导入</h2>
    </div>

    <!-- upload_files：拖拽上传、多文件/目录批量并发上传 -->
    <div class="card">
      <div class="dropzone" @dragover.prevent @drop.prevent="onDrop" @click="triggerFile">
        <div class="dropzone-icon">⬆</div>
        <p class="dropzone-text">拖拽尽调 / 投研 / 投决 / 协议 / 投后文件到此，或点击选择</p>
        <p class="dropzone-hint">支持多文件 / 目录批量上传</p>
        <input ref="fileInput" type="file" multiple hidden @change="onFileChange" />
      </div>

      <!-- poll_import_progress：解析状态进度与结果 -->
      <ul v-if="fileList.length" class="progress">
        <li v-for="(f, i) in fileList" :key="i" class="progress-row">
          <span class="progress-name">{{ f.name }}</span>
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: f.progress + '%' }"></div>
          </div>
          <span class="tag" :class="f.progress === 100 ? 'badge-success' : 'badge-warning'">{{ f.status }}（{{ f.progress }}%）</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { importDocuments } from '../../api/knowledge'

const fileList = ref([])
const fileInput = ref(null)

function triggerFile() {
  fileInput.value?.click()
}

// upload_files：文件落盘后立即返回 task_id，后台异步处理
async function upload_files(files) {
  fileList.value = files.map((f) => ({ name: f.name, status: '上传中', progress: 10 }))
  try {
    const res = await importDocuments(files)
    fileList.value = fileList.value.map((f) => ({ ...f, status: '处理中', progress: 30 }))
    poll_import_progress(res.task_id)
  } catch (err) {
    fileList.value = fileList.value.map((f) => ({
      ...f, status: '失败', progress: 0,
    }))
  }
}

async function poll_import_progress(taskId) {
  const { pollImportProgress } = await import('../../api/knowledge')
  const tick = async () => {
    try {
      const data = await pollImportProgress(taskId)
      const taskStatus = data.status || 'processing'
      const total = data.total_files || fileList.value.length
      const processed = data.processed_files || 0
      const hasError = data.error

      // 按已创建知识单元数判断进度
      const itemCount = (data.items || []).length

      fileList.value = fileList.value.map((f, i) => {
        if (hasError) {
          return { ...f, status: '失败', progress: 0 }
        }
        // 任务已完成
        if (taskStatus === 'done') {
          return { ...f, status: '完成', progress: 100 }
        }
        // 有知识单元产出且全部 active
        if (itemCount > 0 && (data.items || []).every((it) => it.status === 'active')) {
          return { ...f, status: '完成', progress: 100 }
        }
        // 按已处理文件数估算进度
        const pct = 30 + Math.round((processed / Math.max(total, 1)) * 60)
        return { ...f, status: '处理中', progress: Math.min(pct, 90) }
      })

      // 继续轮询直到全部完成或有错误
      if (!hasError && taskStatus !== 'done' && fileList.value.some((f) => f.progress < 100)) {
        setTimeout(tick, 1500)
      }
    } catch {
      // 轮询失败，稍后重试
      setTimeout(tick, 3000)
    }
  }
  tick()
}

function onDrop(e) {
  upload_files([...e.dataTransfer.files])
}

function onFileChange(e) {
  upload_files([...e.target.files])
}
</script>

<style scoped>
.dropzone {
  border: 2px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-bg-subtle);
  padding: var(--space-10);
  text-align: center;
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.dropzone:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.dropzone-icon {
  font-size: 32px;
  color: var(--color-primary);
  margin-bottom: var(--space-2);
}

.dropzone-text {
  color: var(--color-text);
  font-size: var(--font-size-base);
}

.dropzone-hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  margin-top: var(--space-2);
}

.progress {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.progress-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.progress-name {
  width: 200px;
  flex-shrink: 0;
  font-size: var(--font-size-sm);
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-track {
  flex: 1;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--color-bg-hover);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  transition: width var(--transition-base);
}
</style>
