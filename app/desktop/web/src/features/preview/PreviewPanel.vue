<script setup lang="ts">
defineProps<{ file?: string | null }>()
</script>

<template>
  <div class="preview-page">
    <header class="preview-header">
      <h1 id="preview-title">预览</h1>
    </header>
    <section class="preview-card" aria-labelledby="preview-title">
      <p class="preview-empty" role="status">{{ file == null ? '-' : file.split('/').pop() || '尚未加载程序' }}</p>
    </section>
  </div>
</template>

<style scoped>
.preview-page {
  min-height: 100svh;
  display: flex;
  flex-direction: column;
  padding: 18px 18px 18px 0;
}

.preview-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid rgb(255 255 255 / 90%);
  border-radius: 32px;
  background:
    radial-gradient(ellipse at 50% 48%, rgb(231 235 241 / 38%), transparent 70%),
    linear-gradient(135deg, rgb(255 255 255 / 92%), rgb(255 255 255 / 55%) 50%, rgb(255 255 255 / 88%));
  box-shadow: 0 12px 36px rgb(34 43 61 / 4%), inset 0 0 0 1px rgb(255 255 255 / 70%);
  backdrop-filter: blur(24px) saturate(140%);
}

.preview-header {
  padding: 12px 24px 22px;
}

.preview-header h1 { font-size: 18px; font-weight: 600; letter-spacing: -0.03em; }

.preview-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #93959c;
  font-size: 14px;
  font-weight: 500;
}

@media (prefers-reduced-transparency: reduce) {
  .preview-card { background: #fafafb; backdrop-filter: none; }
}
</style>
