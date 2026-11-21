<script setup lang="ts">
// The content card originally used for spindle and work-coordinate readouts.
withDefaults(defineProps<{ as?: 'div' | 'section' | 'article' | 'button' }>(), { as: 'div' })
</script>

<template>
  <component :is="as" class="readout">
    <slot />
  </component>
</template>

<style scoped>
.readout {
  padding: 12px 18px;
  border-radius: var(--readout-radius, 16px);
  background: rgb(255 255 255 / 78%);
  box-shadow: var(--shadow-xs);
}

button.readout {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  text-align: start;
  cursor: pointer;
}

button.readout:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 2px;
}
</style>
