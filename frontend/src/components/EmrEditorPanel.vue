<template>
  <div class="emr-editor-panel">
    <div class="panel-header">
      <div>
        <h3>病历草稿编辑区</h3>
        <p>生成后可直接在此审阅和修订，导出前请完成医生确认。</p>
      </div>
    </div>

    <div v-if="riskAlerts.length > 0" class="risk-alerts">
      <el-alert
        v-for="(alert, i) in riskAlerts"
        :key="i"
        :title="alert"
        type="warning"
        show-icon
        :closable="false"
        class="risk-item"
      />
    </div>

    <div class="editor-wrapper">
      <el-input
        type="textarea"
        :model-value="emrText"
        @update:model-value="$emit('update:emrText', $event)"
        :autosize="{ minRows: 18, maxRows: 40 }"
        placeholder="完成诊断后将在此显示病历草稿，可直接编辑..."
      />
    </div>
  </div>
</template>

<script setup>
defineProps({
  emrText: { type: String, default: '' },
  riskAlerts: { type: Array, default: () => [] },
})

defineEmits(['update:emrText'])
</script>

<style scoped>
.emr-editor-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
}

.panel-header {
  margin-bottom: 16px;
}

.panel-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}

.panel-header p {
  margin: 6px 0 0;
  color: var(--medical-muted);
  font-size: 13px;
}

.risk-alerts {
  margin-bottom: 14px;
}

.risk-item {
  margin-bottom: 8px;
}

.editor-wrapper {
  flex: 1;
}

.editor-wrapper :deep(.el-textarea__inner) {
  min-height: 100%;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.8;
  color: var(--medical-text);
  border-radius: 14px;
}
</style>
