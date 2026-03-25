<template>
  <div class="admin-page">
    <div class="page-toolbar medical-card">
      <div>
        <div class="medical-section-title">语音识别配置</div>
        <div class="toolbar-desc">管理腾讯云实时语音识别 API 配置，激活后用于问诊实时转写</div>
      </div>
      <el-button type="primary" @click="openCreate">新增配置</el-button>
    </div>

    <div class="medical-card table-card">
      <el-table :data="configs" style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="appid" label="AppID" width="140" />
        <el-table-column prop="secret_id_masked" label="SecretId" min-width="180" />
        <el-table-column prop="engine_model_type" label="引擎类型" width="160" />
        <el-table-column label="状态" width="180">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '已启用' : '已停用' }}</el-tag>
            <el-tag v-if="row.is_active" type="primary" class="ml8">当前激活</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="success" @click="testConfig(row)">测试</el-button>
            <el-button link @click="toggleEnable(row)">{{ row.is_enabled ? '停用' : '启用' }}</el-button>
            <el-button link type="warning" :disabled="!row.is_enabled || row.is_active" @click="activate(row)">设为激活</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <AsrConfigFormDialog
      v-model:visible="dialogVisible"
      :initial-value="currentConfig"
      @submit="submitForm"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listAsrConfigs,
  createAsrConfig,
  updateAsrConfig,
  deleteAsrConfig,
  activateAsrConfig,
  enableAsrConfig,
  testAsrConfig,
} from '../../api'
import AsrConfigFormDialog from '../../components/admin/AsrConfigFormDialog.vue'

const configs = ref([])
const dialogVisible = ref(false)
const currentConfig = ref(null)

async function loadConfigs() {
  const { data } = await listAsrConfigs()
  configs.value = data
}

function openCreate() {
  currentConfig.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  currentConfig.value = row
  dialogVisible.value = true
}

async function submitForm(payload) {
  try {
    if (currentConfig.value?.id) {
      await updateAsrConfig(currentConfig.value.id, payload)
      ElMessage.success('ASR 配置已更新')
    } else {
      await createAsrConfig(payload)
      ElMessage.success('ASR 配置已创建')
    }
    dialogVisible.value = false
    await loadConfigs()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  }
}

async function testConfig(row) {
  const loading = ElMessage({ message: '正在测试连接...', duration: 0, type: 'info' })
  try {
    const { data } = await testAsrConfig(row.id)
    loading.close()
    ElMessage[data.success ? 'success' : 'warning'](data.message)
  } catch (error) {
    loading.close()
    ElMessage.error(error?.response?.data?.detail || '测试失败')
  }
}

async function toggleEnable(row) {
  await enableAsrConfig(row.id, !row.is_enabled)
  ElMessage.success('状态已更新')
  await loadConfigs()
}

async function activate(row) {
  await activateAsrConfig(row.id)
  ElMessage.success('已切换当前激活 ASR 配置')
  await loadConfigs()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除配置"${row.name}"吗？`, '提示', { type: 'warning' })
  await deleteAsrConfig(row.id)
  ElMessage.success('删除成功')
  await loadConfigs()
}

onMounted(loadConfigs)
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

.ml8 {
  margin-left: 8px;
}
</style>
