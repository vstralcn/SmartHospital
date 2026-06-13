<template>
  <div class="admin-login medical-page">
    <div class="login-card medical-card">
      <div class="login-header">
        <div class="badge">MED</div>
        <h1>管理员登录</h1>
        <p>默认账号：admin / admin123</p>
      </div>

      <el-form :model="form" @submit.prevent="handleLogin">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入管理员账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit-btn" @click="handleLogin">
          登录后台
        </el-button>
      </el-form>

      <div class="login-footer">
        <el-button text size="small" @click="goDoctor">返回医生入口</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { loginAdmin } from '../../api'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin123' })

async function handleLogin() {
  loading.value = true
  try {
    const { data } = await loginAdmin(form)
    localStorage.setItem('admin_token', data.token)
    localStorage.setItem('admin_user', JSON.stringify(data.user))
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/admin/dashboard')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

function goDoctor() {
  router.push('/login')
}
</script>

<style scoped>
.admin-login {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.login-card {
  width: min(460px, 100%);
  padding: 32px;
}

.login-header {
  text-align: center;
  margin-bottom: 24px;
}

.badge {
  width: 60px;
  height: 60px;
  border-radius: 18px;
  margin: 0 auto 16px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--medical-primary), var(--medical-accent));
  color: #fff;
  font-size: 20px;
  font-weight: 700;
}

.login-header h1 {
  margin: 0;
  font-size: 28px;
}

.login-header p {
  margin: 8px 0 0;
  color: var(--medical-muted);
}

.submit-btn {
  width: 100%;
}

.login-footer {
  margin-top: 16px;
  text-align: center;
}
</style>
