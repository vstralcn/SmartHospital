<template>
  <div class="structured-panel">
    <div class="panel-header">
      <div>
        <h3>结构化病历字段</h3>
        <p>可直接审核并修订主诉、现病史等核心内容。</p>
      </div>
    </div>

    <div v-if="!structured" class="empty-hint">完成诊断后将在此显示结构化信息</div>

    <div v-else class="fields-list">
      <div v-for="field in fields" :key="field.key" class="field-card">
        <div class="field-label">{{ field.label }}</div>
        <div class="field-value" :contenteditable="true" @blur="onFieldEdit(field.key, $event)">{{ getFieldValue(field.key) || '待补充' }}</div>
      </div>

      <div v-if="structured.missing_info && structured.missing_info.length > 0" class="field-card warning-card">
        <div class="field-label">缺失信息</div>
        <div class="field-value">
          <el-tag v-for="(item, i) in structured.missing_info" :key="i" type="warning" size="small" class="tag-item">{{ item }}</el-tag>
        </div>
      </div>

      <div v-if="structured.needs_confirmation && structured.needs_confirmation.length > 0" class="field-card confirm-card">
        <div class="field-label">待确认项</div>
        <div class="field-value">
          <el-tag v-for="(item, i) in structured.needs_confirmation" :key="i" type="info" size="small" class="tag-item">{{ item }}</el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  structured: { type: Object, default: null },
})

const emit = defineEmits(['update:structured'])

const fields = [
  { key: 'chief_complaint', label: '主诉' },
  { key: 'present_illness', label: '现病史' },
  { key: 'past_history', label: '既往史' },
  { key: 'surgical_history', label: '手术史' },
  { key: 'allergy_history', label: '过敏史' },
  { key: 'medication_history', label: '用药史' },
  { key: 'family_history', label: '家族史' },
]

function getFieldValue(key) {
  return props.structured ? props.structured[key] || '' : ''
}

function onFieldEdit(key, event) {
  if (!props.structured) return
  const newValue = event.target.innerText.trim()
  emit('update:structured', { ...props.structured, [key]: newValue })
}
</script>

<style scoped>
.structured-panel {
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

.empty-hint {
  text-align: center;
  color: var(--medical-muted);
  padding: 40px 16px;
}

.fields-list {
  flex: 1;
  overflow: auto;
}

.field-card {
  margin-bottom: 14px;
  padding: 14px;
  border: 1px solid var(--medical-border);
  border-radius: 14px;
  background: #fbfdff;
}

.warning-card {
  background: #fff8eb;
  border-color: #f1cd87;
}

.confirm-card {
  background: #f4f8fd;
}

.field-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--medical-muted);
  margin-bottom: 6px;
}

.field-value {
  font-size: 14px;
  color: var(--medical-text);
  line-height: 1.7;
  min-height: 24px;
  outline: none;
}

.tag-item {
  margin: 2px 6px 2px 0;
}
</style>
