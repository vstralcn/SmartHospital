<template>
  <div class="diagnosis-page medical-page">
    <DoctorNav class="page-nav" />
    <DisclaimerBanner />

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
      :statusLabel="statusLabel"
      @start="handleStart"
      @complete="handleComplete"
      @save="handleSave"
      @export-docx="handleExportDocx"
      @open-settings="showSettings = true"
    />

    <SettingsDialog v-model:visible="showSettings" />
  </div>
</template>

<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { ElMessage, ElLoading, ElMessageBox } from 'element-plus'
import DoctorNav from '../components/DoctorNav.vue'
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
    localStorage.setItem('active_session_id', sessionId.value)
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
</script>

<style scoped>
.diagnosis-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  width: 100%;
}

.page-nav {
  margin: 12px 16px 0;
}

.main-content {
  display: grid;
  grid-template-columns: minmax(280px, 1.05fr) minmax(280px, 0.95fr) minmax(320px, 1fr);
  flex: 1;
  gap: 16px;
  padding: 0 16px 8px;
  min-height: 0;
  overflow: hidden;
}

.panel {
  overflow: auto;
  min-height: 0;
  height: 100%;
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
  .main-content {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .right-panel {
    grid-column: auto;
  }
}

@media (max-width: 768px) {
  .main-content {
    padding-left: 12px;
    padding-right: 12px;
  }
}
</style>
