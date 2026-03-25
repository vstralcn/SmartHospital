<template>
  <el-dialog v-model="visibleProxy" :title="isEdit ? '编辑语音识别配置' : '新增语音识别配置'" width="640px">
    <el-form :model="form" label-width="120px">
      <el-form-item label="配置名称">
        <el-input v-model="form.name" placeholder="如：腾讯云 ASR 生产环境" />
      </el-form-item>
      <el-form-item label="AppID">
        <el-input v-model="form.appid" placeholder="腾讯云账号 AppID" />
      </el-form-item>
      <el-form-item label="SecretId">
        <el-input v-model="form.secret_id" placeholder="API 密钥 SecretId" />
      </el-form-item>
      <el-form-item label="SecretKey">
        <el-input v-model="form.secret_key" type="password" show-password placeholder="编辑时留空表示不修改" />
      </el-form-item>
      <el-form-item label="引擎模型类型">
        <el-select v-model="form.engine_model_type">
          <el-option label="16k 中文 (16k_zh)" value="16k_zh" />
          <el-option label="16k 中英混合 (16k_zh_en)" value="16k_zh_en" />
          <el-option label="16k 英文 (16k_en)" value="16k_en" />
          <el-option label="16k 粤语 (16k_ca)" value="16k_ca" />
          <el-option label="16k 中文方言 (16k_zh_dialect)" value="16k_zh_dialect" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="form.is_enabled">启用该配置</el-checkbox>
        <el-checkbox v-model="form.is_active">设为当前激活</el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visibleProxy = false">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="saving">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, watch, ref } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialValue: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'submit'])
const saving = ref(false)

const form = reactive({
  name: '',
  appid: '',
  secret_id: '',
  secret_key: '',
  engine_model_type: '16k_zh',
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
      appid: props.initialValue?.appid || '',
      secret_id: props.initialValue?.secret_id || '',
      secret_key: '',
      engine_model_type: props.initialValue?.engine_model_type || '16k_zh',
      is_enabled: props.initialValue?.is_enabled ?? true,
      is_active: props.initialValue?.is_active ?? false,
    })
  },
  { immediate: true }
)

async function handleSubmit() {
  saving.value = true
  try {
    await emit('submit', { ...form })
  } finally {
    saving.value = false
  }
}
</script>
