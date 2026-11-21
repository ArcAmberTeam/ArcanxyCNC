<script setup lang="ts" generic="T extends string | number">
// 轴配置页中「轴方案」和「运动学模型」共用的下拉选择器。
// Shared dropdown for the axis profile and kinematics model on the Axis Configuration page.
import { computed } from 'vue'
import { Check, ChevronDown } from '@lucide/vue'
import {
  DropdownMenuContent, DropdownMenuPortal, DropdownMenuRadioGroup,
  DropdownMenuRadioItem, DropdownMenuRoot, DropdownMenuTrigger,
} from 'reka-ui'
import { Card } from '@/components/ui/card'

interface Choice<Value> {
  value: Value
  label: string
  detail?: string
  note?: string
  description?: string
  disabled?: boolean
}
const props = defineProps<{ label: string; modelValue: T | null; choices: readonly Choice<T>[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
const current = computed(() => props.choices.find(choice => choice.value === props.modelValue))
</script>

<template>
  <DropdownMenuRoot :modal="false">
    <DropdownMenuTrigger as-child>
      <Card as="button" type="button" class="group min-h-12 w-full min-w-0 text-sm font-medium">
        <span class="shrink-0">{{ label }}</span>
        <span class="flex min-w-0 items-center gap-2 text-muted-foreground">
          <span class="truncate">{{ current?.label ?? '-' }}{{ current?.detail ? ' · ' + current.detail : '' }}</span>
          <ChevronDown aria-hidden="true" class="size-4 shrink-0 transition-transform group-data-[state=open]:rotate-180" />
        </span>
      </Card>
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent :aria-label="label" side="bottom" align="start" :side-offset="4" :collision-padding="8"
        class="z-50 max-h-(--reka-dropdown-menu-content-available-height) w-(--reka-dropdown-menu-trigger-width) overflow-y-auto rounded-xl border bg-popover p-1 text-popover-foreground shadow-md outline-none data-[state=open]:animate-in data-[side=bottom]:slide-in-from-top-2 motion-reduce:animate-none">
        <DropdownMenuRadioGroup :model-value="modelValue">
          <DropdownMenuRadioItem v-for="choice in choices" :key="choice.value" v-slot="{ checked }"
            :value="choice.value" :disabled="choice.disabled" :aria-description="choice.description || undefined"
            class="flex min-h-11 items-center gap-3 rounded-lg px-3 py-2 text-sm outline-none data-highlighted:bg-accent data-disabled:text-muted-foreground"
            @select="emit('update:modelValue', choice.value)">
            <span class="min-w-0 flex-1">
              <span class="font-medium">{{ choice.label }}</span>
              <span v-if="choice.detail !== undefined" class="ml-2 text-muted-foreground">{{ choice.detail || '-' }}</span>
              <span v-if="choice.note" class="ml-2">{{ choice.note }}</span>
            </span>
            <Check v-if="checked" class="size-4 shrink-0 text-primary" aria-hidden="true" />
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
