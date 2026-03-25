<template>
  <el-dialog v-model="visibleProxy" :title="isEdit ? '编辑模型配置' : '新增模型配置'" width="640px">
    <el-form :model="form" label-width="110px">
      <el-form-item label="配置名称">
        <el-input v-model="form.name" placeholder="如：OpenAI 生产环境" />
      </el-form-item>
      <el-form-item label="提供商">
        <el-select v-model="form.provider">
          <el-option label="Mock" value="mock" />
          <el-option label="OpenAI 兼容" value="openai" />
          <el-option label="本地模型" value="local" />
        </el-select>
      </el-form-item>
      <el-form-item label="模型名称">
        <el-input v-model="form.model" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input v-model="form.api_key" type="password" show-password placeholder="编辑时留空表示不修改" />
      </el-form-item>
      <el-form-item label="Base URL">
        <el-input v-model="form.base_url" placeholder="https://api.openai.com/v1" />
      </el-form-item>
      <el-form-item label="Temperature">
        <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" :precision="1" />
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="form.is_enabled">启用该配置</el-checkbox>
        <el-checkbox v-model="form.is_active">设为当前激活</el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleTest" :loading="testing">测试连通性</el-button>
      <el-button @click="visibleProxy = false">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="saving">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, watch, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { testModelPayload } from '../../api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialValue: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'submit'])
const saving = ref(false)
const testing = ref(false)

const form = reactive({
  name: '',
  provider: 'mock',
  model: 'gpt-4o-mini',
  api_key: '',
  base_url: '',
  temperature: 1.0,
  is_enabled: true,
  is_active: false,
})

const visibleProxy = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const isEdit = computed(() => !!props.initialValue?.id)

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    Object.assign(form, {
      name: props.initialValue?.name || '',
      provider: props.initialValue?.provider || 'mock',
      model: props.initialValue?.model || 'gpt-4o-mini',
      api_key: '',
      base_url: props.initialValue?.base_url || '',
      temperature: props.initialValue?.temperature ?? 1.0,
      is_enabled: props.initialValue?.is_enabled ?? true,
      is_active: props.initialValue?.is_active ?? false,
    })
  },
  { immediate: true }
)

async function handleTest() {
  testing.value = true
  try {
    const { data } = await testModelPayload({ ...form })
    ElMessage[data.success ? 'success' : 'warning'](data.message)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '测试失败')
  } finally {
    testing.value = false
  }
}

async function handleSubmit() {
  saving.value = true
  try {
    await emit('submit', { ...form })
  } finally {
    saving.value = false
  }
}
</script>
