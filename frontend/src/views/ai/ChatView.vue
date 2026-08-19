<template>
  <div class="chat">
    <!-- render_history_list：历史会话侧边栏（深色） -->
    <aside class="chat-sessions">
      <!-- send_question：新建对话 = 回到空态 -->
      <button class="session-new-btn" @click="new_session">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M8 2v12M2 8h12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        新对话
      </button>
      <nav class="session-list">
        <div
          v-for="s in sessions"
          :key="s.session_id"
          class="session-item"
          :class="{ active: s.session_id === currentSessionId }"
          @click="selectSession(s)"
        >
          {{ s.title || s.session_id.slice(0, 8) }}
        </div>
      </nav>
      <div class="session-footer">
        <router-link to="/dashboard" class="session-back">← 返回数据看板</router-link>
      </div>
    </aside>

    <!-- 消息线程（浅色） -->
    <main class="chat-thread">
      <div class="thread-scroll">
        <div class="thread-inner">
          <!-- 空态：无消息时的欢迎页 -->
          <div v-if="!messages.length" class="chat-empty">
            <div class="empty-logo">◆</div>
            <h2>投融资智能问答</h2>
            <p>询问项目尽调、投决、投后等投融资问题…</p>
          </div>

          <!-- 消息流 -->
          <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
            <!-- 用户消息：右侧气泡 -->
            <template v-if="m.role === 'user'">
              <div class="msg-bubble">{{ m.content }}</div>
            </template>
            <!-- 助理消息：左侧头像 + 流式 Markdown -->
            <template v-else>
              <div class="msg-assistant-inner">
                <span class="avatar assistant">AI</span>
                <div class="msg-body">
                  <!-- render_stage_indicator：检索/思考/生成过程提示 -->
                  <div v-if="m.stage && m.stage !== 'done'" class="stage-indicator" :class="`stage-${m.stage}`">
                    <span class="stage-dot"></span>
                    <span class="stage-text">{{ stageText(m.stage) }}</span>
                    <span v-if="m.stage === 'generating'" class="stage-detail">{{ m.retrievedCount ? `（已命中 ${m.retrievedCount} 个相关片段）` : '' }}</span>
                  </div>
                  <!-- render_stream_markdown：流式 Markdown 渲染 -->
                  <StreamMarkdown :content="m.content" />
                  <!-- render_reference_card：引用来源卡片 -->
                  <ReferenceCard v-if="m.sources?.length" :sources="m.sources" />
                  <!-- render_permission_missing_card：无权限提示卡片 -->
                  <PermissionMissingCard v-if="m.unauthorized?.length" :units="m.unauthorized" />
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- send_question：智能提问输入框 -->
      <form class="composer" @submit.prevent="send_question">
        <div class="composer-box">
          <textarea
            v-model="question"
            rows="1"
            placeholder="询问项目尽调、投决、投后等投融资问题…"
            @keydown.enter.exact.prevent="send_question"
          />
          <button type="submit" class="send-btn" :disabled="!question.trim()">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 8l8-5-2.5 9.5L6.5 9.5 4 8z" fill="currentColor" />
              <path d="M6.5 9.5L12 3" stroke="currentColor" stroke-width="1.5" />
            </svg>
          </button>
        </div>
        <p class="composer-hint">ChatGPT 可以犯错，请核查重要信息</p>
      </form>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { chatStream as chatStreamApi, listHistorySessions } from '../../api/ai'
import StreamMarkdown from '../../components/StreamMarkdown.vue'
import ReferenceCard from '../../components/ReferenceCard.vue'
import PermissionMissingCard from '../../components/PermissionMissingCard.vue'

const sessions = ref([])
const messages = ref([])
const question = ref('')
let currentSessionId = null

// new_session：新建对话 = 清空消息、回到空态
function new_session() {
  currentSessionId = null
  messages.value = []
  question.value = ''
}

// send_question：发起智能提问（SSE 流式）
async function send_question() {
  if (!question.value.trim()) return
  const q = question.value
  messages.value.push({ role: 'user', content: q })
  const assistant = { role: 'assistant', content: '', sources: [], unauthorized: [], stage: 'retrieving', retrievedCount: 0 }
  messages.value.push(assistant)
  question.value = ''
  await chatStreamApi(q, currentSessionId, {
    onEvent(event, data) {
      if (event === 'status') {
        assistant.stage = data.stage
      } else if (event === 'trace') {
        currentSessionId = data.session_id
        // 授权片段数用于生成阶段的展示
        assistant.retrievedCount = (data.authorized_unit_ids || []).length
      } else if (event === 'answer') {
        assistant.stage = 'generating'
        assistant.content += data.chunk
      } else if (event === 'sources') {
        assistant.sources = data
      } else if (event === 'permission_missing') {
        assistant.unauthorized = data.units || data.unit_ids || []
      } else if (event === 'error') {
        assistant.stage = 'done'
        assistant.content = (assistant.content || '') + `\n\n[错误] ${data.message || '请求失败'}`
      } else if (event === 'done') {
        assistant.stage = 'done'
        render_history_list()
      }
    },
  }).catch((err) => {
    assistant.stage = 'done'
    assistant.content = (assistant.content || '') + `\n\n[错误] 无法连接服务：${err?.message || err}`
  })
}

// stage_text：检索/思考/生成阶段文案
function stageText(stage) {
  return {
    retrieving: '正在检索知识库…',
    thinking: '正在分析并组织回答…',
    generating: '正在生成回答…',
  }[stage] || stage
}

async function render_history_list() {
  sessions.value = await listHistorySessions()
}

async function selectSession(s) {
  currentSessionId = s.session_id
  const { listSessionMessages } = await import('../../api/ai')
  messages.value = await listSessionMessages(s.session_id)
  nextTick(scroll_to_bottom)
}

function scroll_to_bottom() {
  const el = document.querySelector('.thread-scroll')
  if (el) el.scrollTop = el.scrollHeight
}

onMounted(() => {
  render_history_list()
})
</script>

<style scoped>
.chat {
  display: flex;
  height: 100vh;
  background: var(--color-bg);
}

/* ---------- 会话侧边栏 ---------- */
.chat-sessions {
  width: var(--sidebar-width);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-sidebar);
}

.session-new-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3);
  color: var(--color-sidebar-text);
  background: var(--color-sidebar-active);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.session-new-btn:hover {
  background: var(--color-sidebar-hover);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-item {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--color-sidebar-text);
  font-size: var(--font-size-sm);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background var(--transition-fast);
}

.session-item:hover {
  background: var(--color-sidebar-hover);
}

.session-item.active {
  background: var(--color-sidebar-active);
}

.session-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  padding-top: var(--space-3);
}

.session-back {
  color: var(--color-sidebar-text-muted);
  font-size: var(--font-size-sm);
  transition: color var(--transition-fast);
}

.session-back:hover {
  color: var(--color-sidebar-text);
}

/* ---------- 消息线程 ---------- */
.chat-thread {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.thread-scroll {
  flex: 1;
  overflow-y: auto;
}

.thread-inner {
  max-width: var(--chat-max-width);
  margin: 0 auto;
}

.msg {
  padding: var(--space-4) var(--space-5);
}

.msg.user {
  background: var(--color-bg-subtle);
}

.msg.assistant {
  background: var(--color-bg);
}

.msg-bubble {
  max-width: 80%;
  margin-left: auto;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: var(--line-height-base);
}

.msg-assistant-inner {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
}

.avatar {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}

.avatar.assistant {
  background: var(--color-primary);
  color: var(--color-primary-contrast);
}

.msg-body {
  flex: 1;
  min-width: 0;
}

/* ---------- 阶段指示器（检索/思考/生成过程） ---------- */
.stage-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  border: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.stage-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--color-text-muted);
  animation: stage-pulse 1.2s ease-in-out infinite;
}
.stage-retrieving .stage-dot { background: var(--color-accent); }
.stage-thinking  .stage-dot { background: #b7791f; }
.stage-generating .stage-dot { background: var(--color-primary); }
.stage-text {
  font-weight: var(--font-weight-medium);
}
.stage-detail {
  color: var(--color-text-muted);
}
@keyframes stage-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

/* ---------- 空态欢迎页 ---------- */
.chat-empty {
  text-align: center;
  padding: var(--space-12) var(--space-4);
  color: var(--color-text-secondary);
}

.empty-logo {
  width: 48px;
  height: 48px;
  margin: 0 auto var(--space-4);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: var(--color-primary-contrast);
  font-size: var(--font-size-lg);
}

.chat-empty h2 {
  color: var(--color-text);
  font-size: var(--font-size-xl);
  margin-bottom: var(--space-2);
}

.chat-empty p {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

/* ---------- Composer ---------- */
.composer {
  padding: var(--space-3) var(--space-4) var(--space-4);
  background: var(--color-bg);
}

.composer-box {
  max-width: var(--chat-max-width);
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  padding: var(--space-2);
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.composer-box:focus-within {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-focus);
}

.composer textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  font: inherit;
  font-size: var(--font-size-base);
  color: var(--color-text);
  padding: var(--space-2) var(--space-3);
  line-height: 1.5;
  max-height: 160px;
}

.composer textarea::placeholder {
  color: var(--color-text-muted);
}

.send-btn {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: var(--color-primary-contrast);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.send-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.send-btn:disabled {
  background: var(--color-bg-hover);
  color: var(--color-text-muted);
  cursor: not-allowed;
}

.composer-hint {
  max-width: var(--chat-max-width);
  margin: var(--space-2) auto 0;
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}
</style>
