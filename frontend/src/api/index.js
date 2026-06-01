import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

api.interceptors.request.use((config) => {
  const url = config.url || ''
  let token = ''
  if (url.startsWith('/admin/')) {
    token = localStorage.getItem('admin_token') || ''
  } else {
    token = localStorage.getItem('doctor_token') || localStorage.getItem('admin_token') || ''
  }
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export function getAdminToken() {
  return localStorage.getItem('admin_token') || ''
}

export function getDoctorToken() {
  return localStorage.getItem('doctor_token') || ''
}

export function getDoctorUser() {
  const raw = localStorage.getItem('doctor_user')
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function startDiagnosis(doctorId) {
  return api.post('/diagnosis/start', { doctor_id: doctorId || null })
}

export function transcribeDialogues(sessionId, dialogues) {
  return api.post('/diagnosis/transcribe', {
    session_id: sessionId,
    dialogues,
  })
}

export function completeDiagnosis(sessionId) {
  return api.post('/diagnosis/complete', {
    session_id: sessionId,
  })
}

export function generateEMR(sessionId) {
  return api.post('/diagnosis/generate-emr', {
    session_id: sessionId,
  })
}

export function getFollowUp(sessionId) {
  return api.get('/diagnosis/follow-up', {
    params: { session_id: sessionId },
  })
}

export function exportDocx(sessionId, emrText = '', emrHtml = '') {
  return api.post(
    '/export/docx',
    { session_id: sessionId, emr_text: emrText, emr_html: emrHtml },
    { responseType: 'blob' }
  )
}

export function exportJson(sessionId, emrText = '', emrHtml = '') {
  return api.post('/export/json', {
    session_id: sessionId,
    emr_text: emrText,
    emr_html: emrHtml,
  })
}

export function getSettings() {
  return api.get('/settings')
}

export function updateSettings(payload) {
  return api.put('/settings', payload)
}

export function loginAdmin(payload) {
  return api.post('/admin/auth/login', payload)
}

export function getCurrentAdmin() {
  return api.get('/admin/auth/me')
}

export function logoutAdmin() {
  return api.post('/admin/auth/logout')
}

export function listModelConfigs() {
  return api.get('/admin/models')
}

export function createModelConfig(payload) {
  return api.post('/admin/models', payload)
}

export function updateModelConfig(id, payload) {
  return api.put(`/admin/models/${id}`, payload)
}

export function deleteModelConfig(id) {
  return api.delete(`/admin/models/${id}`)
}

export function activateModelConfig(id) {
  return api.post(`/admin/models/${id}/activate`)
}

export function enableModelConfig(id, enabled) {
  return api.post(`/admin/models/${id}/enable`, null, { params: { enabled } })
}

export function testModelConfig(id) {
  return api.post(`/admin/models/${id}/test`)
}

export function testModelPayload(payload) {
  return api.post('/admin/models/test', payload)
}

export function listDoctors() {
  return api.get('/admin/doctors')
}

export function createDoctor(payload) {
  return api.post('/admin/doctors', payload)
}

export function updateDoctor(id, payload) {
  return api.put(`/admin/doctors/${id}`, payload)
}

export function enableDoctor(id, enabled) {
  return api.post(`/admin/doctors/${id}/enable`, null, { params: { enabled } })
}

export function resetDoctorPassword(id) {
  return api.post(`/admin/doctors/${id}/reset-password`)
}

// --- Admin ASR Config ---
export function listAsrConfigs() {
  return api.get('/admin/asr')
}

export function createAsrConfig(payload) {
  return api.post('/admin/asr', payload)
}

export function updateAsrConfig(id, payload) {
  return api.put(`/admin/asr/${id}`, payload)
}

export function deleteAsrConfig(id) {
  return api.delete(`/admin/asr/${id}`)
}

export function activateAsrConfig(id) {
  return api.post(`/admin/asr/${id}/activate`)
}

export function enableAsrConfig(id, enabled) {
  return api.post(`/admin/asr/${id}/enable`, null, { params: { enabled } })
}

export function testAsrConfig(id) {
  return api.post(`/admin/asr/${id}/test`)
}

// --- Doctor Auth ---
export function loginDoctor(payload) {
  return api.post('/doctor/auth/login', payload)
}

export function getDoctorMe() {
  return api.get('/doctor/auth/me')
}

export function logoutDoctor() {
  return api.post('/doctor/auth/logout')
}

// --- Consultation Records ---
export function listConsultations(page = 1, pageSize = 20) {
  return api.get('/consultations', { params: { page, page_size: pageSize } })
}

export function getConsultation(id) {
  return api.get(`/consultations/${id}`)
}

export function saveConsultation(sessionId, patientName = '') {
  return api.post('/consultations', { session_id: sessionId, patient_name: patientName })
}

export function deleteConsultation(id) {
  return api.delete(`/consultations/${id}`)
}

// --- Multi-Agent Monitor ---
export function getAgentPipeline() {
  return api.get('/agents/pipeline')
}

export function getMcpServers() {
  return api.get('/agents/servers')
}

export function listAgentRuns(limit = 20) {
  return api.get('/agents/runs', { params: { limit } })
}

export function getAgentRunByTask(taskId) {
  return api.get(`/agents/runs/${taskId}`)
}

export function getAgentRunBySession(sessionId) {
  return api.get(`/agents/runs/session/${sessionId}`)
}

export function getLatestAgentRun() {
  return api.get('/agents/runs/latest')
}

export default api
