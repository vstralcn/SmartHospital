<template>
  <div class="admin-page">
    <div class="page-toolbar medical-card">
      <div>
        <div class="medical-section-title">模型 API 管理</div>
        <div class="toolbar-desc">统一维护多套模型配置、启停状态与当前激活项</div>
      </div>
      <el-button type="primary" @click="openCreate">新增配置</el-button>
    </div>

    <div class="medical-card table-card">
      <el-table :data="models" style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="provider" label="Provider" width="120" />
        <el-table-column prop="model" label="模型" min-width="180" />
        <el-table-column prop="api_key_masked" label="API Key" min-width="160" />
        <el-table-column label="状态" width="180">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '已启用' : '已停用' }}</el-tag>
            <el-tag v-if="row.is_active" type="primary" class="ml8">当前激活</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
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

    <ModelConfigFormDialog
      v-model:visible="dialogVisible"
      :initial-value="currentModel"
      @submit="submitForm"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  activateModelConfig,
  createModelConfig,
  deleteModelConfig,
  enableModelConfig,
  listModelConfigs,
  testModelConfig,
  updateModelConfig,
} from '../../api'
import ModelConfigFormDialog from '../../components/admin/ModelConfigFormDialog.vue'

const models = ref([])
const dialogVisible = ref(false)
const currentModel = ref(null)

async function loadModels() {
  const { data } = await listModelConfigs()
  models.value = data
}

function openCreate() {
  currentModel.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  currentModel.value = row
  dialogVisible.value = true
}

async function submitForm(payload) {
  try {
    if (currentModel.value?.id) {
      await updateModelConfig(currentModel.value.id, payload)
      ElMessage.success('模型配置已更新')
    } else {
      await createModelConfig(payload)
      ElMessage.success('模型配置已创建')
    }
    dialogVisible.value = false
    await loadModels()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  }
}

async function testConfig(row) {
  const { data } = await testModelConfig(row.id)
  ElMessage[data.success ? 'success' : 'warning'](data.message)
}

async function toggleEnable(row) {
  await enableModelConfig(row.id, !row.is_enabled)
  ElMessage.success('状态已更新')
  await loadModels()
}

async function activate(row) {
  await activateModelConfig(row.id)
  ElMessage.success('已切换当前激活模型')
  await loadModels()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除配置“${row.name}”吗？`, '提示', { type: 'warning' })
  await deleteModelConfig(row.id)
  ElMessage.success('删除成功')
  await loadModels()
}

onMounted(loadModels)
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
  gap: 16px;
  flex-wrap: wrap;
}

.toolbar-desc {
  margin-top: 6px;
  color: var(--medical-muted);
}

.table-card {
  overflow-x: auto;
}

.ml8 {
  margin-left: 8px;
}
</style>
