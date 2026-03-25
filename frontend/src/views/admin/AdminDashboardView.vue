<template>
  <div class="dashboard-page">
    <section class="stats-grid">
      <div class="stat-card medical-card">
        <div class="label">当前激活模型</div>
        <div class="value">{{ activeModel?.name || '未配置' }}</div>
        <div class="meta">{{ activeModel?.provider || '-' }} / {{ activeModel?.model || '-' }}</div>
      </div>
      <div class="stat-card medical-card">
        <div class="label">模型配置总数</div>
        <div class="value">{{ stats.modelCount }}</div>
        <div class="meta">已启用 {{ stats.enabledCount }} 条</div>
      </div>
      <div class="stat-card medical-card">
        <div class="label">语音识别配置</div>
        <div class="value">{{ activeAsr?.name || '未配置' }}</div>
        <div class="meta">{{ activeAsr?.engine_model_type || '-' }}</div>
      </div>
      <div class="stat-card medical-card">
        <div class="label">医生账号数</div>
        <div class="value">{{ stats.doctorCount }}</div>
        <div class="meta">含在职与停用账号</div>
      </div>
    </section>

    <section class="medical-card info-card">
      <div class="medical-section-title">系统概览</div>
      <ul>
        <li>模型配置统一由数据库管理，激活后问诊页将直接使用当前活动配置。</li>
        <li>API Key 在列表中默认脱敏展示，编辑时留空表示不修改。</li>
        <li>可在“模型配置”中执行连通性测试与启用切换。</li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { listDoctors, listModelConfigs, listAsrConfigs } from '../../api'

const models = ref([])
const doctors = ref([])
const asrConfigs = ref([])
const stats = reactive({ modelCount: 0, enabledCount: 0, doctorCount: 0 })
const activeModel = computed(() => models.value.find((item) => item.is_active))
const activeAsr = computed(() => asrConfigs.value.find((item) => item.is_active))

async function loadData() {
  const [modelRes, doctorRes, asrRes] = await Promise.all([listModelConfigs(), listDoctors(), listAsrConfigs()])
  models.value = modelRes.data
  doctors.value = doctorRes.data
  asrConfigs.value = asrRes.data
  stats.modelCount = models.value.length
  stats.enabledCount = models.value.filter((item) => item.is_enabled).length
  stats.doctorCount = doctors.value.length
}

onMounted(loadData)
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
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
  word-break: break-word;
}

.meta {
  margin-top: 8px;
  color: var(--medical-muted);
  word-break: break-word;
}

.info-card {
  padding: 24px;
}

.info-card ul {
  margin: 16px 0 0;
  padding-left: 20px;
  color: var(--medical-text);
  line-height: 1.8;
}
</style>
