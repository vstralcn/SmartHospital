import { createRouter, createWebHistory } from 'vue-router'
import DoctorLoginView from '../views/DoctorLoginView.vue'
import DiagnosisView from '../views/DiagnosisView.vue'
import ConsultationHistoryView from '../views/ConsultationHistoryView.vue'
import AgentMonitorView from '../views/AgentMonitorView.vue'
import AdminLayout from '../layouts/AdminLayout.vue'
import AdminLoginView from '../views/admin/AdminLoginView.vue'
import AdminDashboardView from '../views/admin/AdminDashboardView.vue'
import AdminModelsView from '../views/admin/AdminModelsView.vue'
import AdminAsrView from '../views/admin/AdminAsrView.vue'
import AdminDoctorsView from '../views/admin/AdminDoctorsView.vue'
import { getAdminToken, getDoctorToken, getDoctorMe, getCurrentAdmin } from '../api/index'

const routes = [
  {
    path: '/',
    redirect: () => {
      return getDoctorToken() ? '/diagnosis' : '/login'
    },
  },
  { path: '/login', name: 'doctor-login', component: DoctorLoginView },
  {
    path: '/diagnosis',
    name: 'diagnosis',
    component: DiagnosisView,
    meta: { requiresDoctorAuth: true },
  },
  {
    path: '/consultations',
    name: 'consultations',
    component: ConsultationHistoryView,
    meta: { requiresDoctorAuth: true },
  },
  {
    path: '/agent-monitor',
    name: 'agent-monitor',
    component: AgentMonitorView,
    meta: { requiresDoctorAuth: true },
  },
  { path: '/admin/login', name: 'admin-login', component: AdminLoginView },
  {
    path: '/admin',
    component: AdminLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', name: 'admin-dashboard', component: AdminDashboardView },
      { path: 'models', name: 'admin-models', component: AdminModelsView },
      { path: 'asr', name: 'admin-asr', component: AdminAsrView },
      { path: 'doctors', name: 'admin-doctors', component: AdminDoctorsView },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  // Doctor auth guard
  if (to.meta.requiresDoctorAuth) {
    const token = getDoctorToken()
    if (!token) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    try {
      await getDoctorMe()
    } catch {
      localStorage.removeItem('doctor_token')
      localStorage.removeItem('doctor_user')
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  // Admin auth guard
  if (to.meta.requiresAuth) {
    const token = getAdminToken()
    if (!token) {
      return { path: '/admin/login', query: { redirect: to.fullPath } }
    }
    try {
      await getCurrentAdmin()
    } catch {
      localStorage.removeItem('admin_token')
      localStorage.removeItem('admin_user')
      return { path: '/admin/login', query: { redirect: to.fullPath } }
    }
  }

  // Already logged in redirects
  if (to.path === '/login' && getDoctorToken()) {
    return '/diagnosis'
  }
  if (to.path === '/admin/login' && getAdminToken()) {
    return '/admin/dashboard'
  }

  return true
})

export default router
