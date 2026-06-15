<template>
  <div class="control-bar medical-card">
    <div class="left-section">
      <el-button v-if="status === 'idle'" type="primary" @click="$emit('start')">开始诊断</el-button>
      <el-button v-if="status === 'idle' || status === 'done'" plain @click="$emit('demo')">使用 Demo 数据</el-button>
      <el-button v-if="status === 'recording'" type="danger" @click="$emit('complete')">完成诊断</el-button>
      <el-button v-if="status === 'done'" type="primary" @click="$emit('start')">新诊断</el-button>
      <el-button v-if="status === 'done'" type="success" @click="$emit('save')">保存记录</el-button>
      <el-button v-if="status === 'done'" @click="$emit('export-docx')">导出 Word</el-button>
    </div>

    <div class="center-section">
      <span v-if="status === 'idle'" class="status-text">系统就绪，点击"开始诊断"进入实时问诊</span>
      <span v-else-if="status === 'recording'" class="status-text recording"><span class="dot"></span> 正在采集并整理问诊内容</span>
      <span v-else-if="status === 'generating'" class="status-text">正在生成病历草稿，请稍候...</span>
      <span v-else-if="status === 'done'" class="status-text done">病历草稿已生成，等待医生审核</span>
    </div>

    <div class="right-section">
      <span class="status-chip">
        <i>状态</i><strong>{{ statusLabel }}</strong>
      </span>
      <span class="status-chip">
        <i>会话 ID</i><strong>{{ sessionId || '未开始' }}</strong>
      </span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  status: { type: String, default: 'idle' },
  isRecording: { type: Boolean, default: false },
  sessionId: { type: String, default: '' },
  statusLabel: { type: String, default: '' },
})

defineEmits(['start', 'complete', 'save', 'export-docx', 'open-settings', 'demo'])
</script>

<style scoped>
.control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 0 16px 8px;
  padding: 10px 20px;
  flex-shrink: 0;
}

.left-section,
.right-section {
  display: flex;
  gap: 8px;
  align-items: center;
}

.center-section {
  flex: 1;
  text-align: center;
}

.status-text {
  font-size: 14px;
  color: var(--medical-muted);
}

.status-text.recording {
  color: #d9534f;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-text.done {
  color: var(--medical-accent);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d9534f;
  animation: blink 1s infinite;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 10px;
  background: var(--medical-primary-light);
  white-space: nowrap;
}

.status-chip i {
  font-style: normal;
  color: var(--medical-muted);
  font-size: 12px;
}

.status-chip strong {
  font-size: 13px;
  color: var(--medical-primary);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}
</style>
