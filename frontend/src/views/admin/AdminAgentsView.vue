<template>
  <div class="admin-page">
    <section class="stats-grid">
      <div class="stat-card medical-card">
        <div class="label">运行任务数</div>
        <div class="value">{{ stats.task_total }}</div>
        <div class="meta">累计触发的问诊流水线</div>
      </div>
      <div class="stat-card medical-card">
        <div class="label">智能体执行次数</div>
        <div class="value">{{ stats.execution_total }}</div>
        <div class="meta">各智能体节点累计执行</div>
      </div>
      <div class="stat-card medical-card">
        <div class="label">累计 Token</div>
        <div class="value">{{ stats.token_total }}</div>
        <div class="meta">全部运行的 Token 总消耗</div>
      </div>
      <div class="stat-card medical-card">
        <div class="label">异常次数</div>
        <div class="value">{{ stats.error_total }}</div>
        <div class="meta">状态为 error 的执行</div>
      </div>
    </section>

    <section class="medical-card pipeline-card">
      <div class="medical-section-title">协作流水线（{{ pipeline.length }} 节点）</div>
      <div class="pipeline">
        <template v-for="(node, idx) in pipeline" :key="node.name">
          <div class="pipeline-node">
            <div class="node-label">{{ node.label }}</div>
            <div class="node-name">{{ node.name }}</div>
            <div class="node-desc">{{ node.description }}</div>
          </div>
          <span v-if="idx < pipeline.length - 1" class="pipeline-arrow">→</span>
        </template>
      </div>
    </section>

    <div class="page-toolbar medical-card">
      <div>
        <div class="medical-section-title">运行记录</div>
        <div class="toolbar-desc">查看历史运行与每个智能体的输入输出、工具调用</div>
      </div>
      <el-button :loading="loading" @click="loadRuns">刷新</el-button>
    </div>

    <div class="medical-card table-card">
      <el-table v-loading="loading" :data="runs" style="width: 100%">
        <el-table-column prop="task_id" label="任务 ID" min-width="200" show-overflow-tooltip />
        <el-table-column prop="session_id" label="会话 ID" min-width="180" show-overflow-tooltip />
        <el-table-column label="节点" width="90">
          <template #default="{ row }">{{ row.agent_count }}</template>
        </el-table-column>
        <el-table-column label="Token" width="100">
          <template #default="{ row }">{{ row.total_tokens }}</template>
        </el-table-column>
        <el-table-column label="耗时(ms)" width="110">
          <template #default="{ row }">{{ row.duration_ms }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'error' ? 'danger' : 'success'" effect="plain">
              {{ row.status === 'error' ? '异常' : '成功' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openRun(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !runs.length" description="暂无运行记录，触发一次问诊后展示" />
    </div>

    <section class="medical-card servers-card">
      <div class="medical-section-title">MCP 服务</div>
      <div class="servers">
        <div v-for="server in servers" :key="server.name" class="server">
          <div class="server-name">{{ server.name }}</div>
          <div class="server-tools">
            <el-tag v-for="tool in server.tools || []" :key="tool" size="small" effect="plain">{{ tool }}</el-tag>
          </div>
        </div>
        <el-empty v-if="!servers.length" description="无 MCP 服务" :image-size="60" />
      </div>
    </section>

    <el-drawer v-model="runVisible" title="运行详情" size="52%">
      <div v-if="currentRun" class="run-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="任务 ID">{{ currentRun.task_id }}</el-descriptions-item>
        </el-descriptions>
        <el-collapse v-model="activeAgents" class="agent-collapse">
          <el-collapse-item v-for="log in currentRun.logs" :key="log.id" :name="String(log.id)">
            <template #title>
              <span class="agent-title">
                <el-tag :type="log.status === 'error' ? 'danger' : 'success'" size="small" effect="plain">
                  {{ labelOf(log.agent_name) }}
                </el-tag>
                <span class="agent-meta">{{ log.total_tokens }} tokens · {{ log.duration_ms }} ms</span>
              </span>
            </template>
            <div v-if="log.tool_calls && log.tool_calls.length" class="agent-section">
              <div class="agent-section-title">工具调用</div>
              <el-tag
                v-for="(call, i) in log.tool_calls"
                :key="i"
                type="warning"
                effect="plain"
                class="tool-tag"
              >{{ toolName(call) }}</el-tag>
            </div>
            <div class="agent-section">
              <div class="agent-section-title">输入</div>
              <pre class="payload">{{ pretty(log.input_payload) }}</pre>
            </div>
            <div class="agent-section">
              <div class="agent-section-title">输出</div>
              <pre class="payload">{{ pretty(log.output_payload) }}</pre>
            </div>
            <el-alert v-if="log.error" :title="log.error" type="error" :closable="false" show-icon />
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import {
  getAgentPipeline,
  getAgentRunByTask,
  getAgentStats,
  getMcpServers,
  listAgentRuns,
} from '../../api'

const stats = reactive({ task_total: 0, execution_total: 0, token_total: 0, error_total: 0 })
const pipeline = ref([])
const runs = ref([])
const servers = ref([])
const loading = ref(false)

const runVisible = ref(false)
const currentRun = ref(null)
const activeAgents = ref([])

function labelOf(name) {
  const node = pipeline.value.find((n) => n.name === name)
  return node ? `${node.label} · ${name}` : name
}

function toolName(call) {
  if (typeof call === 'string') return call
  return call?.name || call?.tool || JSON.stringify(call)
}

function pretty(value) {
  if (value == null) return '（空）'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

async function loadRuns() {
  loading.value = true
  try {
    const [runRes, statRes] = await Promise.all([listAgentRuns(50), getAgentStats()])
    runs.value = runRes.data.runs
    Object.assign(stats, statRes.data)
  } finally {
    loading.value = false
  }
}

async function openRun(row) {
  const { data } = await getAgentRunByTask(row.task_id)
  currentRun.value = data
  activeAgents.value = (data.logs || []).map((l) => String(l.id))
  runVisible.value = true
}

onMounted(async () => {
  const [pipeRes, serverRes] = await Promise.all([getAgentPipeline(), getMcpServers()])
  pipeline.value = pipeRes.data.pipeline
  servers.value = serverRes.data.servers
  await loadRuns()
})
</script>

<style scoped>
.admin-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.stat-card {
  padding: 24px;
  min-width: 0;
}

.label {
  color: var(--medical-muted);
  font-size: 14px;
}

.value {
  margin-top: 10px;
  font-size: clamp(24px, 2vw, 28px);
  font-weight: 700;
}

.meta {
  margin-top: 8px;
  color: var(--medical-muted);
}

.pipeline-card,
.servers-card,
.page-toolbar,
.table-card {
  padding: 20px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-desc {
  margin-top: 6px;
  color: var(--medical-muted);
}

.pipeline {
  display: flex;
  align-items: stretch;
  gap: 10px;
  margin-top: 16px;
  overflow-x: auto;
  padding-bottom: 6px;
}

.pipeline-node {
  flex: 0 0 150px;
  border: 1px solid var(--el-border-color, #e4e7ed);
  border-radius: 10px;
  padding: 12px;
}

.node-label {
  font-weight: 700;
}

.node-name {
  color: var(--medical-muted);
  font-size: 12px;
  margin: 2px 0 6px;
}

.node-desc {
  font-size: 12px;
  line-height: 1.5;
}

.pipeline-arrow {
  align-self: center;
  color: var(--medical-muted);
}

.servers {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-top: 16px;
}

.server-name {
  font-weight: 600;
  margin-bottom: 8px;
}

.server-tools {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.agent-collapse {
  margin-top: 16px;
}

.agent-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.agent-meta {
  color: var(--medical-muted);
  font-size: 12px;
}

.agent-section {
  margin-bottom: 12px;
}

.agent-section-title {
  font-weight: 600;
  margin-bottom: 6px;
}

.tool-tag {
  margin: 0 6px 6px 0;
}

.payload {
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--medical-surface, #f7f9fc);
  border-radius: 8px;
  padding: 10px;
  margin: 0;
  max-height: 220px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.6;
}
</style>
