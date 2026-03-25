<template>
  <div class="admin-layout medical-page">
    <aside class="sidebar medical-card">
      <div class="brand">
        <div class="brand-badge">MED</div>
        <div>
          <div class="brand-title">医疗管理后台</div>
          <div class="brand-subtitle">Hospital Admin Console</div>
        </div>
      </div>
      <el-menu :default-active="activeMenu" router class="menu">
        <el-menu-item index="/admin/dashboard">概览</el-menu-item>
        <el-menu-item index="/admin/models">模型配置</el-menu-item>
        <el-menu-item index="/admin/asr">语音识别</el-menu-item>
        <el-menu-item index="/admin/doctors">医生账号</el-menu-item>
      </el-menu>
    </aside>

    <div class="content-area">
      <header class="topbar medical-card">
        <div>
          <div class="page-title">管理员后台</div>
          <div class="page-desc">统一管理模型配置、账号与系统状态</div>
        </div>
        <div class="topbar-actions">
          <el-dropdown>
            <span class="admin-user">{{ adminName }}</span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="page-body">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { logoutAdmin } from '../api'

const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => route.path)
const adminName = computed(() => {
  const raw = localStorage.getItem('admin_user')
  if (!raw) return '管理员'
  try {
    return JSON.parse(raw).username || '管理员'
  } catch {
    return '管理员'
  }
})

async function handleLogout() {
  try {
    await logoutAdmin()
  } catch {
    // ignore
  }
  localStorage.removeItem('admin_token')
  localStorage.removeItem('admin_user')
  ElMessage.success('已退出登录')
  router.push('/admin/login')
}
</script>

<style scoped>
.admin-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 20px;
  min-height: 100vh;
  padding: 20px;
}

.sidebar {
  padding: 20px 14px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px 20px;
}

.brand-badge {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--medical-primary), var(--medical-accent));
  color: #fff;
  font-weight: 700;
}

.brand-title {
  font-size: 18px;
  font-weight: 700;
}

.brand-subtitle {
  font-size: 12px;
  color: var(--medical-muted);
}

.menu {
  background: transparent;
}

.content-area {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.topbar {
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
}

.page-desc {
  margin-top: 6px;
  color: var(--medical-muted);
  font-size: 14px;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.admin-user {
  font-weight: 600;
  color: var(--medical-primary);
  cursor: pointer;
}

.page-body {
  min-width: 0;
}

@media (max-width: 960px) {
  .admin-layout {
    grid-template-columns: 1fr;
  }
}
</style>
