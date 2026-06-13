<template>
  <div class="admin-page">
    <section class="stats-grid">
      <div class="stat-card medical-card">
        <div class="label">病例总数</div>
        <div class="value">{{ stats.total }}</div>
        <div class="meta">全部医生已保存的问诊记录</div>
      </div>
      <div class="stat-card medical-card">
        <div class="label">涉及医生数</div>
        <div class="value">{{ stats.doctorCount }}</div>
        <div class="meta">有病例记录的接诊医生</div>
      </div>
    </section>

    <div class="page-toolbar medical-card">
      <div>
        <div class="medical-section-title">病例管理</div>
        <div class="toolbar-desc">查看与管理全部医生的问诊病历</div>
      </div>
      <div class="toolbar-filters">
        <el-select
          v-model="doctorFilter"
          placeholder="全部医生"
          clearable
          style="width: 180px"
          @change="reload"
        >
          <el-option
            v-for="d in doctors"
            :key="d.id"
            :label="`${d.full_name}（${d.department || '未填科室'}）`"
            :value="d.id"
          />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="搜索患者 / 病历 / 会话 ID"
          clearable
          style="width: 240px"
          @keyup.enter="reload"
          @clear="reload"
        />
        <el-button type="primary" @click="reload">查询</el-button>
      </div>
    </div>

    <div class="medical-card table-card">
      <el-table v-loading="loading" :data="records" style="width: 100%">
        <el-table-column prop="patient_name" label="患者" min-width="120">
          <template #default="{ row }">{{ row.patient_name || '未填写' }}</template>
        </el-table-column>
        <el-table-column label="接诊医生" min-width="160">
          <template #default="{ row }">
            <div>{{ row.doctor_name }}</div>
            <div class="cell-sub">{{ row.department || '未填科室' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="病历摘要" min-width="260">
          <template #default="{ row }">
            <span class="cell-sub">{{ row.emr_text_preview || '（空）' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : 'info'" effect="plain">
              {{ row.status === 'done' ? '已完成' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看详情</el-button>
            <el-button link type="danger" @click="removeRecord(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
    </div>

    <el-drawer v-model="detailVisible" title="病例详情" size="46%">
      <div v-if="detail" class="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="患者">{{ detail.patient_name || '未填写' }}</el-descriptions-item>
          <el-descriptions-item label="接诊医生">{{ detail.doctor_name }} · {{ detail.department || '未填科室' }}</el-descriptions-item>
          <el-descriptions-item label="会话 ID">{{ detail.session_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detail.risk_alerts && detail.risk_alerts.length" class="detail-block">
          <div class="medical-section-title">风险提示</div>
          <el-alert
            v-for="(alert, idx) in detail.risk_alerts"
            :key="idx"
            :title="typeof alert === 'string' ? alert : (alert.message || JSON.stringify(alert))"
            type="warning"
            :closable="false"
            show-icon
            class="risk-alert"
          />
        </div>

        <div v-if="structuredEntries.length" class="detail-block">
          <div class="medical-section-title">结构化病历字段</div>
          <el-descriptions :column="1" border>
            <el-descriptions-item
              v-for="item in structuredEntries"
              :key="item.key"
              :label="item.key"
            >{{ item.value }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="detail-block">
          <div class="medical-section-title">病历全文</div>
          <pre class="emr-text">{{ detail.emr_text || '（空）' }}</pre>
        </div>

        <div v-if="detail.dialogues && detail.dialogues.length" class="detail-block">
          <div class="medical-section-title">对话记录（{{ detail.dialogues.length }} 条）</div>
          <el-table :data="detail.dialogues" size="small" max-height="260">
            <el-table-column prop="speaker" label="角色" width="120">
              <template #default="{ row }">{{ row.speaker || row.role || '-' }}</template>
            </el-table-column>
            <el-table-column label="内容">
              <template #default="{ row }">{{ row.text || row.content || '' }}</template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  adminConsultationStats,
  adminDeleteConsultation,
  adminGetConsultation,
  adminListConsultations,
  listDoctors,
} from '../../api'

const records = ref([])
const doctors = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const keyword = ref('')
const doctorFilter = ref(null)
const stats = reactive({ total: 0, doctorCount: 0 })

const detailVisible = ref(false)
const detail = ref(null)

const structuredEntries = computed(() => {
  const s = detail.value?.structured
  if (!s || typeof s !== 'object') return []
  return Object.entries(s)
    .filter(([, v]) => v != null && String(v).trim() !== '')
    .map(([key, value]) => ({ key, value: String(value) }))
})

async function loadStats() {
  const { data } = await adminConsultationStats()
  stats.total = data.total
  stats.doctorCount = data.doctor_count
}

async function loadRecords() {
  loading.value = true
  try {
    const { data } = await adminListConsultations({
      page: page.value,
      pageSize,
      doctorId: doctorFilter.value,
      q: keyword.value,
    })
    records.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  loadRecords()
}

function onPageChange(p) {
  page.value = p
  loadRecords()
}

async function openDetail(row) {
  const { data } = await adminGetConsultation(row.id)
  detail.value = data
  detailVisible.value = true
}

async function removeRecord(row) {
  await ElMessageBox.confirm(
    `确认删除该病例吗？（患者：${row.patient_name || '未填写'}，医生：${row.doctor_name}）`,
    '删除病例',
    { type: 'warning' },
  )
  await adminDeleteConsultation(row.id)
  ElMessage.success('病例已删除')
  await Promise.all([loadRecords(), loadStats()])
}

onMounted(async () => {
  const { data } = await listDoctors()
  doctors.value = data
  await Promise.all([loadStats(), loadRecords()])
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
}

.meta {
  margin-top: 8px;
  color: var(--medical-muted);
}

.page-toolbar,
.table-card {
  padding: 20px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.toolbar-desc {
  margin-top: 6px;
  color: var(--medical-muted);
}

.toolbar-filters {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.cell-sub {
  color: var(--medical-muted);
  font-size: 13px;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.detail-block {
  margin-top: 20px;
}

.risk-alert {
  margin-bottom: 8px;
}

.emr-text {
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--medical-surface, #f7f9fc);
  border-radius: 8px;
  padding: 12px;
  margin: 8px 0 0;
  font-family: inherit;
  line-height: 1.7;
}
</style>
