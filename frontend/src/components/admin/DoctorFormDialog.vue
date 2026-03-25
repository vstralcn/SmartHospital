<template>
  <el-dialog v-model="visibleProxy" :title="isEdit ? '编辑医生账号' : '新增医生账号'" width="560px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="用户名">
        <el-input v-model="form.username" />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="form.full_name" />
      </el-form-item>
      <el-form-item label="科室">
        <el-input v-model="form.department" />
      </el-form-item>
      <el-form-item :label="isEdit ? '重置密码' : '登录密码'">
        <el-input v-model="form.password" type="password" show-password :placeholder="isEdit ? '留空表示不修改' : '可留空自动生成'" />
      </el-form-item>
      <el-form-item>
        <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visibleProxy = false">取消</el-button>
      <el-button type="primary" @click="emit('submit', { ...form })">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialValue: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'submit'])

const form = reactive({
  username: '',
  full_name: '',
  department: '',
  password: '',
  is_active: true,
})

const isEdit = computed(() => !!props.initialValue?.id)
const visibleProxy = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    Object.assign(form, {
      username: props.initialValue?.username || '',
      full_name: props.initialValue?.full_name || '',
      department: props.initialValue?.department || '',
      password: '',
      is_active: props.initialValue?.is_active ?? true,
    })
  },
  { immediate: true }
)
</script>
