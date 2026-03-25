<template>
  <el-dialog v-model="dialogVisible" title="当前模型配置" width="520px" @close="onClose">
    <el-descriptions v-if="settings.llm" :column="1" border>
      <el-descriptions-item label="提供商">{{ settings.llm.provider || '-' }}</el-descriptions-item>
      <el-descriptions-item label="模型">{{ settings.llm.model || '-' }}</el-descriptions-item>
      <el-descriptions-item label="Base URL">{{ settings.llm.base_url || '-' }}</el-descriptions-item>
      <el-descriptions-item label="Temperature">{{ settings.llm.temperature ?? '-' }}</el-descriptions-item>
    </el-descriptions>
    <el-empty v-else description="暂无模型配置" />

    <el-divider />

    <el-form label-width="140px" class="generation-form">
      <el-form-item label="生成刷新频率(秒)">
        <el-input-number v-model="generationInterval" :min="1" :max="3600" :step="1" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button type="primary" :loading="saving" @click="saveSettings">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, updateSettings } from '../api/index'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['update:visible'])

const dialogVisible = ref(false)
const settings = ref({})
const generationInterval = ref(5)
const saving = ref(false)

async function loadSettings() {
  try {
    const res = await getSettings()
    settings.value = res.data || {}
    generationInterval.value = settings.value?.generation?.refresh_interval_seconds || 5
  } catch {
    settings.value = {}
    generationInterval.value = 5
  }
}

watch(
  () => props.visible,
  async (val) => {
    dialogVisible.value = val
    if (val) {
      await loadSettings()
    }
  },
  { immediate: true }
)

watch(dialogVisible, (val) => {
  if (!val) emit('update:visible', false)
})

async function saveSettings() {
  saving.value = true
  try {
    const res = await updateSettings({
      generation: {
        refresh_interval_seconds: generationInterval.value,
      },
    })
    settings.value = res.data || {}
    generationInterval.value = settings.value?.generation?.refresh_interval_seconds || generationInterval.value
    ElMessage.success('设置已保存')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function onClose() {
  emit('update:visible', false)
}
</script>
