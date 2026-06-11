<template>
  <div class="monitor-page medical-page">
    <DoctorNav />
    <header class="monitor-header medical-card">
      <div class="title-block">
        <div class="hero-badge">Internet of Agents</div>
        <h1>多智能体协作监控</h1>
        <p>实时观测问诊 → 诊断 → 知识检索(RAG) → 用药 → 病历 → 质控 → 随访 的智能体协作流水线。</p>
      </div>
      <div class="header-actions">
        <el-tag v-if="taskId" type="info" effect="plain">任务 {{ taskId }}</el-tag>
        <el-switch v-model="autoRefresh" active-text="自动刷新" />
        <el-button :loading="loading" @click="refresh">手动刷新</el-button>
      </div>
    </header>

    <section class="metrics">
      <div class="metric-card medical-card">
        <span class="metric-label">总耗时</span>
        <strong class="metric-value">{{ totalDuration }} ms</strong>
      </div>
      <div class="metric-card medical-card">
        <span class="metric-label">总 Token</span>
        <strong class="metric-value">{{ totalTokens }}</strong>
      </div>
      <div class="metric-card medical-card">
        <span class="metric-label">已完成节点</span>
        <strong class="metric-value">{{ completedCount }} / {{ pipeline.length }}</strong>
      </div>
      <div class="metric-card medical-card">
        <span class="metric-label">整体状态</span>
        <strong class="metric-value">
          <el-tag :type="overallTagType" effect="dark">{{ overallLabel }}</el-tag>
        </strong>
      </div>
    </section>

    <section class="flow-wrapper medical-card">
      <div class="flow-title medical-section-title">Agent 工作流</div>
      <div class="flowchart">
        <template v-for="(node, index) in nodeStates" :key="node.name">
          <div
            class="agent-node"
            :class="[`status-${node.status}`, { active: selectedAgent === node.name }]"
            @click="selectAgent(node.name)"
          >
            <div class="node-top">
              <span class="node-label">{{ node.label }}</span>
              <span class="node-status-dot" :class="`status-${node.status}`"></span>
            </div>
            <div class="node-name">{{ node.name }}</div>
            <div class="node-desc">{{ node.description }}</div>
            <div class="node-stats" v-if="node.log">
              <span>⏱ {{ node.log.duration_ms }} ms</span>
              <span>🔢 {{ node.log.total_tokens }} tok</span>
              <span>🛠 {{ node.log.tool_calls.length }}</span>
            </div>
            <div class="node-stats pending" v-else>等待执行…</div>
            <el-tag class="node-tag" :type="statusTagType(node.status)" size="small" effect="plain">
              {{ statusLabel(node.status) }}
            </el-tag>
          </div>
          <div v-if="index < nodeStates.length - 1" class="flow-arrow" :class="{ lit: node.log }">
            →
          </div>
        </template>
      </div>
    </section>

    <section class="detail-grid">
      <div class="detail-panel medical-card">
        <div class="medical-section-title">节点详情</div>
        <div v-if="selectedLog" class="detail-body">
          <div class="detail-meta">
            <el-tag :type="statusTagType(selectedLog.status)" effect="dark">
              {{ selectedLog.agent_name }} · {{ statusLabel(selectedLog.status) }}
            </el-tag>
            <span class="meta-pill">{{ selectedLog.duration_ms }} ms</span>
            <span class="meta-pill">{{ selectedLog.total_tokens }} tokens</span>
            <span class="meta-pill">LLM×{{ selectedLog.llm_calls }}</span>
          </div>
          <div v-if="selectedLog.error" class="error-box">{{ selectedLog.error }}</div>
          <div class="sub-title">MCP 工具调用</div>
          <div v-if="selectedLog.tool_calls.length" class="tool-list">
            <div v-for="(tool, i) in selectedLog.tool_calls" :key="i" class="tool-row">
              <el-tag size="small" :type="tool.ok ? 'success' : 'danger'">{{ tool.tool }}</el-tag>
              <code>{{ JSON.stringify(tool.args) }}</code>
            </div>
          </div>
          <div v-else class="muted">该节点未调用 MCP 工具</div>
          <div class="sub-title">输出 (Output Payload)</div>
          <pre class="json-box">{{ pretty(selectedLog.output_payload) }}</pre>
        </div>
        <div v-else class="muted detail-empty">点击上方任一智能体节点查看其输入 / 输出与工具调用详情。</div>
      </div>

      <div class="side-panel">
        <div class="runs-panel medical-card">
          <div class="medical-section-title">运行历史</div>
          <el-table :data="runs" size="small" height="220" @row-click="loadRun">
            <el-table-column prop="created_at" label="时间" width="150" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'error' ? 'danger' : 'success'">
                  {{ row.status === 'error' ? '异常' : '成功' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="duration_ms" label="耗时(ms)" />
            <el-table-column prop="total_tokens" label="Token" />
          </el-table>
        </div>

        <div class="mcp-panel medical-card">
          <div class="medical-section-title">MCP 服务</div>
          <div v-for="server in servers" :key="server.server" class="mcp-server">
            <div class="mcp-server-name">{{ server.name }}</div>
            <div class="mcp-tools">
              <el-tag
                v-for="tool in server.tools"
                :key="tool.name"
                size="small"
                effect="plain"
                class="mcp-tool"
              >
                {{ tool.name }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="insight-grid">
      <div class="insight-panel medical-card">
        <div class="medical-section-title">知识参考 (RAG)</div>
        <div v-if="knowledgeResult && knowledgeResult.references && knowledgeResult.references.length">
          <p class="insight-summary">{{ knowledgeResult.summary }}</p>
          <div
            v-for="(ref, i) in knowledgeResult.references"
            :key="i"
            class="reference-card"
          >
            <div class="reference-head">
              <span class="reference-title">{{ ref.title }}</span>
              <el-tag size="small" effect="plain" type="success">相关度 {{ ref.score }}</el-tag>
            </div>
            <div class="reference-snippet">{{ ref.snippet }}</div>
            <div class="reference-source" v-if="ref.source">来源：{{ ref.source }}</div>
          </div>
        </div>
        <div v-else class="muted">尚未检索到知识参考，运行一次问诊后展示。</div>
      </div>

      <div class="insight-panel medical-card">
        <div class="medical-section-title">随访计划</div>
        <div v-if="followUpPlan">
          <div class="followup-row">
            <span class="followup-label">复诊建议</span>
            <span class="followup-value">{{ followUpPlan.next_visit }}</span>
          </div>
          <div class="followup-row">
            <span class="followup-label">复查项目</span>
            <div class="followup-tags">
              <el-tag
                v-for="(item, i) in followUpPlan.review_items"
                :key="i"
                size="small"
                effect="plain"
              >
                {{ item }}
              </el-tag>
            </div>
          </div>
          <div class="followup-row column">
            <span class="followup-label">注意事项</span>
            <ul class="followup-list">
              <li v-for="(item, i) in followUpPlan.precautions" :key="i">{{ item }}</li>
            </ul>
          </div>
        </div>
        <div v-else class="muted">尚未生成随访计划，运行一次问诊后展示。</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import DoctorNav from '../components/DoctorNav.vue'
import {
  getAgentPipeline,
  getMcpServers,
  listAgentRuns,
  getAgentRunBySession,
  getAgentRunByTask,
  getLatestAgentRun,
} from '../api/index'

const route = useRoute()

const pipeline = ref([])
const logs = ref([])
const runs = ref([])
const servers = ref([])
const taskId = ref('')
const selectedAgent = ref('')
const autoRefresh = ref(true)
const loading = ref(false)
const sessionId = ref(route.query.session || '')

let timer = null

const logsByName = computed(() => {
  const map = {}
  for (const log of logs.value) {
    map[log.agent_name] = log
  }
  return map
})

const nodeStates = computed(() =>
  pipeline.value.map((node) => {
    const log = logsByName.value[node.name] || null
    return { ...node, log, status: log ? log.status : 'pending' }
  }),
)

const completedCount = computed(() => logs.value.length)
const totalDuration = computed(() => logs.value.reduce((sum, l) => sum + (l.duration_ms || 0), 0))
const totalTokens = computed(() => logs.value.reduce((sum, l) => sum + (l.total_tokens || 0), 0))

const overallStatus = computed(() => {
  if (logs.value.some((l) => l.status === 'error')) return 'error'
  if (pipeline.value.length && logs.value.length >= pipeline.value.length) return 'success'
  if (logs.value.length > 0) return 'running'
  return 'idle'
})
const overallLabel = computed(
  () => ({ error: '存在异常', success: '已完成', running: '执行中', idle: '空闲' }[overallStatus.value]),
)
const overallTagType = computed(
  () => ({ error: 'danger', success: 'success', running: 'warning', idle: 'info' }[overallStatus.value]),
)

const selectedLog = computed(() => logsByName.value[selectedAgent.value] || null)

const knowledgeResult = computed(() => {
  const log = logsByName.value['knowledge_agent']
  const payload = log && log.output_payload ? log.output_payload.knowledge : null
  return payload || null
})

const followUpPlan = computed(() => {
  const log = logsByName.value['followup_agent']
  const payload = log && log.output_payload ? log.output_payload.follow_up : null
  return payload || null
})

function statusLabel(status) {
  return { success: '成功', error: '异常', running: '执行中', pending: '等待' }[status] || status
}
function statusTagType(status) {
  return { success: 'success', error: 'danger', running: 'warning', pending: 'info' }[status] || 'info'
}

function pretty(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function selectAgent(name) {
  selectedAgent.value = name
}

function applyRun(data) {
  taskId.value = data.task_id || ''
  logs.value = data.logs || []
  if (data.pipeline && data.pipeline.length) {
    pipeline.value = data.pipeline
  }
  if (!selectedAgent.value && logs.value.length) {
    selectedAgent.value = logs.value[logs.value.length - 1].agent_name
  }
}

async function refresh() {
  loading.value = true
  try {
    let res
    if (sessionId.value) {
      res = await getAgentRunBySession(sessionId.value)
    } else {
      res = await getLatestAgentRun()
    }
    applyRun(res.data)
    const runsRes = await listAgentRuns(20)
    runs.value = runsRes.data.runs || []
  } catch {
    // ignore transient polling errors
  } finally {
    loading.value = false
  }
}

async function loadRun(row) {
  if (!row || !row.task_id) return
  sessionId.value = ''
  autoRefresh.value = false
  const res = await getAgentRunByTask(row.task_id)
  selectedAgent.value = ''
  applyRun(res.data)
}


onMounted(async () => {
  try {
    const [pipeRes, serverRes] = await Promise.all([getAgentPipeline(), getMcpServers()])
    pipeline.value = pipeRes.data.pipeline || []
    servers.value = serverRes.data.servers || []
  } catch {
    // pipeline/servers are best-effort
  }
  await refresh()
  timer = setInterval(() => {
    if (autoRefresh.value) refresh()
  }, 1500)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.monitor-page {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 18px 24px;
  gap: 16px;
}

.hero-badge {
  display: inline-block;
  background: var(--medical-primary-light);
  color: var(--medical-primary);
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 999px;
  margin-bottom: 8px;
}

.title-block h1 {
  margin: 0;
  font-size: 24px;
}

.title-block p {
  margin: 6px 0 0;
  color: var(--medical-muted);
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.metric-card {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric-label {
  color: var(--medical-muted);
  font-size: 13px;
}

.metric-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--medical-primary);
}

.flow-wrapper {
  padding: 20px 24px;
}

.flow-title {
  margin-bottom: 16px;
}

.flowchart {
  display: flex;
  align-items: stretch;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 8px;
}

.agent-node {
  flex: 1 1 0;
  min-width: 180px;
  border: 2px solid var(--medical-border);
  border-radius: 14px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.agent-node:hover {
  transform: translateY(-2px);
  box-shadow: var(--medical-shadow);
}

.agent-node.active {
  border-color: var(--medical-primary);
  box-shadow: 0 0 0 3px var(--medical-primary-light);
}

.agent-node.status-success {
  border-color: #2fae7a;
}
.agent-node.status-error {
  border-color: #d9534f;
}
.agent-node.status-running {
  border-color: #e6a23c;
}

.node-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.node-label {
  font-weight: 700;
  font-size: 15px;
}

.node-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #c0c4cc;
}
.node-status-dot.status-success {
  background: #2fae7a;
}
.node-status-dot.status-error {
  background: #d9534f;
}
.node-status-dot.status-running {
  background: #e6a23c;
  animation: blink 1s infinite;
}

.node-name {
  font-size: 11px;
  color: var(--medical-muted);
  font-family: monospace;
}

.node-desc {
  font-size: 12px;
  color: var(--medical-muted);
  min-height: 32px;
}

.node-stats {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: var(--medical-text);
  flex-wrap: wrap;
}

.node-stats.pending {
  color: #c0c4cc;
}

.node-tag {
  align-self: flex-start;
}

.flow-arrow {
  display: flex;
  align-items: center;
  font-size: 24px;
  color: #c0c4cc;
  flex: 0 0 auto;
}
.flow-arrow.lit {
  color: var(--medical-primary);
}

.detail-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 16px;
}

.detail-panel {
  padding: 18px 20px;
  min-height: 320px;
}

.detail-body {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.meta-pill {
  background: var(--medical-primary-light);
  color: var(--medical-primary);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
}

.sub-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--medical-text);
  margin-top: 4px;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-row code {
  font-size: 12px;
  color: var(--medical-muted);
  word-break: break-all;
}

.json-box {
  background: #0f172a;
  color: #d6e4f0;
  border-radius: 10px;
  padding: 12px;
  font-size: 12px;
  max-height: 260px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.error-box {
  background: #fef0f0;
  color: #d9534f;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
}

.muted {
  color: var(--medical-muted);
  font-size: 13px;
}

.detail-empty {
  margin-top: 24px;
}

.side-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.runs-panel,
.mcp-panel {
  padding: 16px 18px;
}

.runs-panel :deep(.el-table) {
  cursor: pointer;
  margin-top: 10px;
}

.mcp-server {
  margin-top: 12px;
}

.mcp-server-name {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 6px;
}

.mcp-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

.insight-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
}

.insight-panel {
  padding: 18px 22px;
}

.insight-summary {
  color: var(--medical-muted);
  font-size: 13px;
  margin: 0 0 12px;
  line-height: 1.6;
}

.reference-card {
  border: 1px solid var(--medical-border, #e4e7ed);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: var(--medical-primary-light, #f5f9ff);
}

.reference-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.reference-title {
  font-weight: 600;
  font-size: 14px;
}

.reference-snippet {
  font-size: 13px;
  line-height: 1.6;
  color: var(--medical-text, #303133);
}

.reference-source {
  margin-top: 6px;
  font-size: 12px;
  color: var(--medical-muted);
}

.followup-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 12px;
}

.followup-row.column {
  flex-direction: column;
}

.followup-label {
  flex: 0 0 72px;
  font-weight: 600;
  font-size: 13px;
  color: var(--medical-primary);
}

.followup-value {
  font-size: 14px;
}

.followup-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.followup-list {
  margin: 4px 0 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 1024px) {
  .metrics {
    grid-template-columns: repeat(2, 1fr);
  }
  .detail-grid {
    grid-template-columns: 1fr;
  }
  .insight-grid {
    grid-template-columns: 1fr;
  }
}
</style>
