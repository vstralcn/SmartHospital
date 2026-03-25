<template>
  <div class="transcript-panel">
    <div class="panel-header">
      <div>
        <h3>问诊对话记录</h3>
        <p>实时展示医生与患者沟通内容，支持追问建议辅助。</p>
      </div>
      <el-tag v-if="isRecording" type="danger" effect="dark" size="small">采集中</el-tag>
    </div>

    <div class="transcript-list">
      <el-table :data="dialogues" style="width: 100%" size="small" max-height="420">
        <el-table-column prop="start" label="时间" width="78">
          <template #default="{ row }">{{ formatTime(row.start) }}</template>
        </el-table-column>
        <el-table-column prop="speaker" label="角色" width="88">
          <template #default="{ row }">
            <el-tag :type="row.speaker === 'doctor' ? 'primary' : 'success'" size="small">
              {{ row.speaker === 'doctor' ? '医生' : '患者' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="text" label="内容" />
      </el-table>
      <div v-if="dialogues.length === 0" class="empty-hint">暂无问诊记录，点击“开始诊断”后即可采集语音或使用 Demo 数据。</div>
    </div>

    <div v-if="partialText" class="partial-text">
      <el-icon class="pulse"><Microphone /></el-icon>
      <span>{{ partialText }}</span>
    </div>

    <div v-if="suggestions.length > 0" class="suggestions">
      <h4>系统追问建议</h4>
      <ul>
        <li v-for="(s, i) in suggestions" :key="i">{{ s }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { Microphone } from '@element-plus/icons-vue'

defineProps({
  dialogues: { type: Array, default: () => [] },
  partialText: { type: String, default: '' },
  suggestions: { type: Array, default: () => [] },
  isRecording: { type: Boolean, default: false },
})

function formatTime(seconds) {
  const s = Math.max(0, Math.floor(seconds))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}
</script>

<style scoped>
.transcript-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.panel-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--medical-text);
}

.panel-header p {
  margin: 6px 0 0;
  color: var(--medical-muted);
  font-size: 13px;
}

.transcript-list {
  flex: 1;
  overflow: auto;
}

.empty-hint {
  text-align: center;
  color: var(--medical-muted);
  padding: 40px 16px;
  font-size: 14px;
}

.partial-text {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  margin-top: 12px;
  background: #fff4f1;
  border-radius: 12px;
  color: #d9534f;
  font-size: 14px;
}

.pulse {
  animation: pulse 1.2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.suggestions {
  margin-top: 14px;
  padding: 14px;
  background: #f1fbf8;
  border-radius: 14px;
}

.suggestions h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 700;
  color: var(--medical-accent);
}

.suggestions ul {
  padding-left: 18px;
  margin: 0;
  font-size: 13px;
  color: var(--medical-text);
  line-height: 1.7;
}
</style>
