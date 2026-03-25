<template>
  <div class="diagnosis-page medical-page">
    <DisclaimerBanner />

    <section class="hero medical-card">
      <div>
        <div class="hero-badge">智能问诊病历系统</div>
        <h1>医疗专业风问诊工作台</h1>
        <p>围绕问诊记录、结构化整理与病历生成构建的一体化辅助界面。</p>
      </div>
      <div class="hero-meta">
        <div class="meta-item" v-if="doctorUser">
          <span>当前医生</span>
          <strong>{{ doctorUser.full_name }}</strong>
        </div>
        <div class="meta-item">
          <span>当前状态</span>
          <strong>{{ statusLabel }}</strong>
        </div>
        <div class="meta-item">
          <span>会话 ID</span>
          <strong>{{ sessionId || '未开始' }}</strong>
        </div>
      </div>
    </section>

    <div class="main-content">
      <div class="panel left-panel medical-card">
        <TranscriptPanel
          :dialogues="dialogues"
          :partialText="partialText"
          :suggestions="suggestions"
          :isRecording="isRecording"
        />
      </div>

      <div class="panel center-panel medical-card">
        <StructuredPanel :structured="structured" @update:structured="structured = $event" />
      </div>

      <div class="panel right-panel medical-card">
        <EmrEditorPanel :emrText="emrText" :riskAlerts="riskAlerts" @update:emrText="emrText = $event" />
      </div>
    </div>

    <ControlBar
      :status="status"
      :isRecording="isRecording"
      :sessionId="sessionId"
      :doctorUser="doctorUser"
      @start="handleStart"
      @complete="handleComplete"
      @save="handleSave"
      @export-docx="handleExportDocx"
      @open-settings="showSettings = true"
      @go-history="goHistory"
      @logout="handleLogout"
    />

    <SettingsDialog v-model:visible="showSettings" />
  </div>
</template>

<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElLoading, ElMessageBox } from 'element-plus'
import TranscriptPanel from '../components/TranscriptPanel.vue'
import StructuredPanel from '../components/StructuredPanel.vue'
import EmrEditorPanel from '../components/EmrEditorPanel.vue'
import ControlBar from '../components/ControlBar.vue'
import SettingsDialog from '../components/SettingsDialog.vue'
import DisclaimerBanner from '../components/DisclaimerBanner.vue'
import { useRecorder } from '../composables/useRecorder'
import {
  startDiagnosis,
  completeDiagnosis,
  transcribeDialogues,
  generateEMR,
  getFollowUp,
  exportDocx,
  saveConsultation,
  getDoctorUser,
  getSettings,
} from '../api/index'

const router = useRouter()
const status = ref('idle')
const sessionId = ref('')
const dialogues = ref([])
const structured = ref(null)
const emrText = ref('')
const riskAlerts = ref([])
const suggestions = ref([])
const showSettings = ref(false)

const doctorUser = ref(getDoctorUser())

const { isRecording, partialText, finalTexts, recordingStartTime, asrMode, asrError, startRecording, stopRecording } =
  useRecorder()

let emrTimer = null
let lastSentIndex = 0
const generationIntervalMs = ref(5000)

const statusLabel = computed(() => {
  if (status.value === 'recording') return '问诊中'
  if (status.value === 'generating') return '生成中'
  if (status.value === 'done') return '已完成'
  return '待开始'
})

watch(
  () => finalTexts.value.length,
  async (newLen) => {
    if (newLen <= lastSentIndex || !sessionId.value) return
    const newTexts = finalTexts.value.slice(lastSentIndex)
    lastSentIndex = newLen

    const segments = newTexts.map((item) => ({
      text: item.text,
      start: item.start ?? 0,
      end: item.end ?? item.start ?? 0,
    }))

    try {
      const res = await transcribeDialogues(sessionId.value, segments)
      dialogues.value = res.data.dialogues || []
    } catch (err) {
      console.error('Failed to send transcription:', err)
    }
  },
)

async function loadGenerationSettings() {
  try {
    const res = await getSettings()
    const seconds = Number(res.data?.generation?.refresh_interval_seconds || 5)
    generationIntervalMs.value = Math.max(1000, seconds * 1000)
  } catch {
    generationIntervalMs.value = 5000
  }
}

function startEmrTimer() {
  stopEmrTimer()
  emrTimer = setInterval(async () => {
    if (!sessionId.value || !dialogues.value.length) return
    try {
      const res = await generateEMR(sessionId.value)
      if (res.data && !res.data.error) {
        structured.value = res.data.structured || null
        emrText.value = res.data.emr_text || ''
        riskAlerts.value = res.data.risk_alerts || []
      }
    } catch (err) {
      console.error('Periodic EMR generation failed:', err)
    }
  }, generationIntervalMs.value)
}

function stopEmrTimer() {
  if (emrTimer) {
    clearInterval(emrTimer)
    emrTimer = null
  }
}

loadGenerationSettings()

onUnmounted(() => {
  stopEmrTimer()
})

async function handleStart() {
  try {
    const doctorId = doctorUser.value?.id || null
    const res = await startDiagnosis(doctorId)
    sessionId.value = res.data.session_id
    dialogues.value = []
    structured.value = null
    emrText.value = ''
    riskAlerts.value = []
    suggestions.value = []
    lastSentIndex = 0

    try {
      await startRecording(sessionId.value)
      status.value = 'recording'
      startEmrTimer()
      ElMessage.success('录音已开始，语音识别服务已连接')
    } catch (e) {
      status.value = 'idle'
      stopEmrTimer()
      if (e.message === 'NO_ASR_CONFIG') {
        ElMessage.warning('未配置语音识别服务，请在管理后台配置腾讯云 ASR')
      } else {
        ElMessage.warning('麦克风或语音识别服务不可用：' + (e.message || '未知错误'))
      }
    }
  } catch (err) {
    status.value = 'idle'
    stopEmrTimer()
    ElMessage.error('启动诊断失败：' + (err.message || '未知错误'))
  }
}

async function handleComplete() {
  const loading = ElLoading.service({ text: '正在生成病历...' })
  try {
    stopRecording()
    stopEmrTimer()
    status.value = 'generating'

    const res = await completeDiagnosis(sessionId.value)
    const data = res.data
    dialogues.value = data.dialogues || []
    structured.value = data.structured || null
    emrText.value = data.emr_text || ''
    riskAlerts.value = data.risk_alerts || []
    status.value = 'done'

    try {
      const followUpRes = await getFollowUp(sessionId.value)
      suggestions.value = followUpRes.data.suggestions || []
    } catch {
      suggestions.value = []
    }

    ElMessage.success('病历生成完成')
  } catch (err) {
    status.value = 'recording'
    ElMessage.error('生成失败：' + (err.message || '未知错误'))
  } finally {
    loading.close()
  }
}

async function handleSave() {
  if (!sessionId.value) return

  try {
    const { value: patientName } = await ElMessageBox.prompt('请输入患者标识（可选）', '保存问诊记录', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：张三 / 门诊001',
    })
    await saveConsultation(sessionId.value, patientName || '')
    ElMessage.success('问诊记录已保存')
  } catch (err) {
    if (err === 'cancel' || err?.action === 'cancel') return
    ElMessage.error('保存失败：' + (err?.response?.data?.detail || err.message || '未知错误'))
  }
}

async function handleExportDocx() {
  try {
    const res = await exportDocx(sessionId.value, emrText.value)
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `medical-emr-${Date.now()}.docx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (err) {
    ElMessage.error('导出失败：' + (err.message || '未知错误'))
  }
}

function goHistory() {
  router.push('/consultations')
}

function handleLogout() {
  localStorage.removeItem('doctor_token')
  localStorage.removeItem('doctor_user')
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.diagnosis-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  width: 100%;
}

.hero {
  margin: 16px;
  padding: clamp(18px, 2.4vw, 28px);
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(280px, 1fr);
  align-items: start;
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
  font-size: clamp(24px, 2.2vw, 30px);
}

.hero p {
  margin: 0;
  color: var(--medical-muted);
}

.hero-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 14px;
  width: 100%;
}

.meta-item {
  min-width: 0;
  padding: 16px 18px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid var(--medical-border);
}

.meta-item span {
  display: block;
  color: var(--medical-muted);
  font-size: 12px;
}

.meta-item strong {
  display: block;
  margin-top: 8px;
  font-size: 16px;
  word-break: break-word;
}

.main-content {
  display: grid;
  grid-template-columns: minmax(280px, 1.05fr) minmax(280px, 0.95fr) minmax(320px, 1fr);
  flex: 1;
  gap: 16px;
  padding: 0 16px 16px;
  min-height: 0;
}

.panel {
  overflow: auto;
  min-height: 0;
}

@media (max-width: 1440px) {
  .main-content {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .right-panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1200px) {
  .hero {
    grid-template-columns: 1fr;
  }

  .main-content {
    grid-template-columns: 1fr;
  }

  .right-panel {
    grid-column: auto;
  }
}

@media (max-width: 768px) {
  .hero,
  .main-content {
    margin: 0;
    padding-left: 12px;
    padding-right: 12px;
  }

  .hero {
    margin: 12px;
  }

  .main-content {
    padding-bottom: 12px;
  }
}
</style>
