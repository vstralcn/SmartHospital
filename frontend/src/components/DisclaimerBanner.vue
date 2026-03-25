<template>
  <div class="disclaimer-banner">
    <el-alert
      title="医疗提示：系统输出仅用于辅助整理问诊记录，最终诊疗结论与病历内容需由医生审核确认。"
      type="warning"
      show-icon
      :closable="true"
    />
  </div>
</template>

<style scoped>
.disclaimer-banner {
  padding: 8px 16px 0;
  flex-shrink: 0;
}
</style>
