<template>
  <header class="doctor-nav medical-card">
    <div class="nav-brand">
      <div class="brand-badge">MED</div>
      <div class="brand-text">
        <div class="brand-title">智能问诊病历系统</div>
        <div class="brand-subtitle">Smart Hospital · 医生工作台</div>
      </div>
    </div>

    <nav class="nav-links">
      <router-link
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        class="nav-link"
        :class="{ active: isActive(link) }"
      >
        <el-icon class="nav-icon"><component :is="link.icon" /></el-icon>
        <span>{{ link.label }}</span>
      </router-link>
    </nav>

    <div class="nav-user">
      <el-dropdown>
        <span class="user-trigger">
          <el-avatar :size="30" class="user-avatar">{{ avatarText }}</el-avatar>
          <span class="user-name">{{ doctorName }}</span>
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>{{ departmentLabel }}</el-dropdown-item>
            <el-dropdown-item divided :icon="Setting" @click="goAdmin">管理员后台</el-dropdown-item>
            <el-dropdown-item :icon="SwitchButton" @click="handleLogout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ChatLineSquare,
  Document,
  Connection,
  ArrowDown,
  Setting,
  SwitchButton,
} from '@element-plus/icons-vue'
import { getDoctorUser, logoutDoctor } from '../api/index'

const route = useRoute()
const router = useRouter()

const links = [
  { to: '/diagnosis', label: '问诊工作台', icon: ChatLineSquare },
  { to: '/consultations', label: '问诊记录', icon: Document },
  { to: '/agent-monitor', label: '智能体监控', icon: Connection },
]

const doctorUser = computed(() => getDoctorUser())
const doctorName = computed(() => doctorUser.value?.full_name || doctorUser.value?.username || '医生')
const departmentLabel = computed(() => doctorUser.value?.department || '未设置科室')
const avatarText = computed(() => (doctorName.value || '医').slice(0, 1))

function isActive(link) {
  return route.path === link.to
}

function goAdmin() {
  router.push('/admin')
}

async function handleLogout() {
  try {
    await logoutDoctor()
  } catch {
    // ignore network errors on logout
  }
  localStorage.removeItem('doctor_token')
  localStorage.removeItem('doctor_user')
  localStorage.removeItem('active_session_id')
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.doctor-nav {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 10px 20px;
  flex-shrink: 0;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.brand-badge {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--medical-primary), var(--medical-accent));
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.brand-title {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.2;
}

.brand-subtitle {
  font-size: 12px;
  color: var(--medical-muted);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--medical-muted);
  text-decoration: none;
  transition: background 0.18s ease, color 0.18s ease;
}

.nav-link:hover {
  background: var(--medical-primary-light);
  color: var(--medical-primary);
}

.nav-link.active {
  background: var(--medical-primary);
  color: #fff;
}

.nav-icon {
  font-size: 16px;
}

.nav-user {
  flex-shrink: 0;
}

.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
  color: var(--medical-text);
}

.user-avatar {
  background: var(--medical-primary);
  color: #fff;
  font-weight: 600;
}

.user-name {
  font-weight: 600;
}

@media (max-width: 768px) {
  .doctor-nav {
    flex-wrap: wrap;
    gap: 12px;
  }

  .brand-subtitle {
    display: none;
  }

  .nav-link span {
    display: none;
  }

  .nav-link {
    padding: 8px 12px;
  }
}
</style>
