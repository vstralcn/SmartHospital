<template>
  <div class="admin-page">
    <div class="page-toolbar medical-card">
      <div>
        <div class="medical-section-title">医生账号管理</div>
        <div class="toolbar-desc">支持新增、编辑、启停与密码重置</div>
      </div>
      <el-button type="primary" @click="openCreate">新增医生</el-button>
    </div>

    <div class="medical-card table-card">
      <el-table :data="doctors" style="width: 100%">
        <el-table-column prop="username" label="用户名" min-width="160" />
        <el-table-column prop="full_name" label="姓名" min-width="140" />
        <el-table-column prop="department" label="科室" min-width="140" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link @click="toggleEnable(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
            <el-button link type="warning" @click="resetPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <DoctorFormDialog
      v-model:visible="dialogVisible"
      :initial-value="currentDoctor"
      @submit="submitForm"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createDoctor, enableDoctor, listDoctors, resetDoctorPassword, updateDoctor } from '../../api'
import DoctorFormDialog from '../../components/admin/DoctorFormDialog.vue'

const doctors = ref([])
const dialogVisible = ref(false)
const currentDoctor = ref(null)

async function loadDoctors() {
  const { data } = await listDoctors()
  doctors.value = data
}

function openCreate() {
  currentDoctor.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  currentDoctor.value = row
  dialogVisible.value = true
}

async function submitForm(payload) {
  try {
    if (currentDoctor.value?.id) {
      await updateDoctor(currentDoctor.value.id, payload)
      ElMessage.success('医生账号已更新')
    } else {
      const { data } = await createDoctor(payload)
      ElMessage.success(data.generated_password ? `医生账号已创建，初始密码：${data.generated_password}` : '医生账号已创建')
    }
    dialogVisible.value = false
    await loadDoctors()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  }
}

async function toggleEnable(row) {
  await enableDoctor(row.id, !row.is_active)
  ElMessage.success('账号状态已更新')
  await loadDoctors()
}

async function resetPassword(row) {
  await ElMessageBox.confirm(`确认重置 ${row.full_name} 的密码吗？`, '提示', { type: 'warning' })
  const { data } = await resetDoctorPassword(row.id)
  ElMessage.success(`新密码：${data.password}`)
}

onMounted(loadDoctors)
</script>

<style scoped>
.admin-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-toolbar,
.table-card {
  padding: 20px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-desc {
  margin-top: 6px;
  color: var(--medical-muted);
}
</style>
