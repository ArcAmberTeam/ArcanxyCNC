<script setup lang="ts">
// 轴参数表单中带单位的数字输入框。
// Numeric input with a unit label for individual axis parameters.
import type { NumericField } from './axis-parameter-fields'

defineProps<{ field: NumericField; name: string; label: string; value: string; unit?: string; disabled?: boolean }>()
const emit = defineEmits<{ change: [value: string] }>()
</script>

<template>
  <label class="flex min-w-0 items-center gap-1 rounded-md border border-input bg-background px-2 focus-within:ring-2 focus-within:ring-ring">
    <input :disabled="disabled" type="number" :name="name" :aria-label="label" :value="value" placeholder="-"
      :step="field.index || field.integer ? 1 : 'any'" :min="field.index || field.positive ? 0 : undefined"
      :data-positive="field.positive || undefined"
      class="h-9 w-full min-w-0 bg-transparent text-right tabular-nums outline-none"
      @input="emit('change', ($event.target as HTMLInputElement).value)" />
    <span v-if="unit || field.unit" class="shrink-0 text-xs text-muted-foreground">{{ unit || field.unit }}</span>
  </label>
</template>
