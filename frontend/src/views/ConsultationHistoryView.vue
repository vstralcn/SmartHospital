<template>
  <div class="consultation-history medical-page">
    <section class="hero medical-card">
      <div>
        <div class="hero-badge">问诊记录</div>
        <h1>历史问诊记录</h1>
        <p>查看和管理已完成的问诊会话记录</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" @click="goBack">返回问诊</el-button>
        <el-button :icon="Connection" @click="goMonitor">智能体监控</el-button>
        <el-button @click="handleLogout">退出登录</el-button>
      </div>
    </section>

    <section class="table-section medical-card">
      <el-table :data="records" v-loading="loading" empty-text="暂无问诊记录" stripe>
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="patient_name" label="患者标识" width="140">
          <template #default="{ row }">
            {{ row.patient_name || '未填写' }}
          </template>
        </el-table-column>
        <el-table-column prop="emr_text_preview" label="病历摘要" min-width="240" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : 'info'" size="small">
              {{ row.status === 'done' ? '已完成' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewRecord(row.id)">查看</el-button>
            <el-button text type="danger" size="small" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="fetchRecords"
        />
      </div>
    </section>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" title="问诊记录详情" width="80%" top="5vh" destroy-on-close>
      <div class="detail-content" v-if="detail" v-loading="detailLoading">
        <div class="detail-meta">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="会话 ID">{{ detail.session_id }}</el-descriptions-item>
            <el-descriptions-item label="患者标识">{{ detail.patient_name || '未填写' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <el-tabs type="border-card" class="detail-tabs">
          <el-tab-pane label="对话记录">
            <div class="dialogue-list" v-if="detail.dialogues && detail.dialogues.length">
              <div
                v-for="(seg, idx) in detail.dialogues"
                :key="idx"
                class="dialogue-item"
                :class="{ doctor: seg.speaker === 'doctor', patient: seg.speaker === 'patient' }"
              >
                <span class="speaker-label">{{ seg.speaker === 'doctor' ? '医生' : '患者' }}</span>
                <span class="dialogue-text">{{ seg.text }}</span>
              </div>
            </div>
            <el-empty v-else description="无对话记录" />
          </el-tab-pane>

          <el-tab-pane label="结构化信息">
            <div v-if="detail.structured" class="structured-info">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="主诉">{{ detail.structured.chief_complaint || '-' }}</el-descriptions-item>
                <el-descriptions-item label="现病史">{{ detail.structured.present_illness || '-' }}</el-descriptions-item>
                <el-descriptions-item label="既往史">{{ detail.structured.past_history || '-' }}</el-descriptions-item>
                <el-descriptions-item label="手术史">{{ detail.structured.surgical_history || '-' }}</el-descriptions-item>
                <el-descriptions-item label="过敏史">{{ detail.structured.allergy_history || '-' }}</el-descriptions-item>
                <el-descriptions-item label="用药史">{{ detail.structured.medication_history || '-' }}</el-descriptions-item>
                <el-descriptions-item label="家族史">{{ detail.structured.family_history || '-' }}</el-descriptions-item>
              </el-descriptions>
            </div>
            <el-empty v-else description="无结构化信息" />
          </el-tab-pane>

          <el-tab-pane label="病历文本">
            <div v-if="detail.emr_text" class="emr-text-block">
              <pre>{{ detail.emr_text }}</pre>
            </div>
            <el-empty v-else description="无病历文本" />
          </el-tab-pane>

          <el-tab-pane label="风险提示" v-if="detail.risk_alerts && detail.risk_alerts.length">
            <el-alert
              v-for="(alert, i) in detail.risk_alerts"
              :key="i"
              :title="alert"
              type="warning"
              :closable="false"
              show-icon
              style="margin-bottom: 8px;"
            />
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'
import { listConsultations, getConsultation, deleteConsultation } from '../api'

const router = useRouter()
const loading = ref(false)
const records = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

onMounted(() => {
  fetchRecords()
})

async function fetchRecords() {
  loading.value = true
  try {
    const { data } = await listConsultations(currentPage.value, pageSize.value)
    records.value = data.items || []
    total.value = data.total || 0
  } catch (err) {
    ElMessage.error('加载记录失败：' + (err?.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

async function viewRecord(id) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    const { data } = await getConsultation(id)
    detail.value = data
  } catch (err) {
    ElMessage.error('加载详情失败')
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

async function confirmDelete(row) {
  try {
    await ElMessageBox.confirm('确定要删除这条问诊记录吗？此操作不可恢复。', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteConsultation(row.id)
    ElMessage.success('记录已删除')
    fetchRecords()
  } catch {
    // cancelled
  }
}

function goBack() {
  router.push('/diagnosis')
}

function goMonitor() {
  router.push('/agent-monitor')
}

function handleLogout() {
  localStorage.removeItem('doctor_token')
  localStorage.removeItem('doctor_user')
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.consultation-history {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 16px;
  gap: 16px;
}

.hero {
  padding: 24px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  background: linear-gradient(135deg, #fafdff 0%, #eef6ff 100%);
}

.hero-badge {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--medical-primary-light);
  color: var(--medical-primary);
  font-size: 12px;
  font-weight: 700;
}

.hero h1 {
  margin: 14px 0 8px;
  font-size: 26px;
}

.hero p {
  margin: 0;
  color: var(--medical-muted);
}

.hero-actions {
  display: flex;
  gap: 10px;
}

.table-section {
  padding: 20px;
  flex: 1;
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.detail-meta {
  margin-bottom: 16px;
}

.detail-tabs {
  min-height: 300px;
}

.dialogue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 400px;
  overflow-y: auto;
  padding: 8px;
}

.dialogue-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #f5f7fa;
}

.dialogue-item.doctor {
  background: var(--medical-primary-light);
}

.dialogue-item.patient {
  background: #f0faf8;
}

.speaker-label {
  flex-shrink: 0;
  font-weight: 700;
  font-size: 13px;
  color: var(--medical-primary);
  min-width: 36px;
}

.dialogue-item.patient .speaker-label {
  color: var(--medical-accent);
}

.dialogue-text {
  font-size: 14px;
  line-height: 1.6;
}

.structured-info {
  padding: 8px;
}

.emr-text-block pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.8;
  padding: 16px;
  background: #f9fafb;
  border-radius: 8px;
}
</style>
