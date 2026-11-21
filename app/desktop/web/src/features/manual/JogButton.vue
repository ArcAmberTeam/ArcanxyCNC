<script setup lang="ts">
// 点动按钮，按住时开始点动，松开或取消时停止。
// Jog pad button that starts a jog while held and stops it on release or cancellation.
import { onUnmounted, ref, watch } from 'vue'
import { Button } from '@/components/ui/button'

const props = defineProps<{ disabled: boolean; cancel: boolean; label: string }>()
const emit = defineEmits<{ start: []; stop: [] }>()
const held = ref(false)
let pointer: number | undefined
let key: string | undefined

function release() {
  pointer = undefined
  key = undefined
  if (!held.value) return
  held.value = false
  emit('stop')
}
function pressPointer(event: PointerEvent) {
  if (props.disabled || held.value || !event.isPrimary || event.button !== 0) return
  event.preventDefault()
  const target = event.currentTarget as HTMLElement
  target.focus()
  target.setPointerCapture(event.pointerId)
  pointer = event.pointerId
  held.value = true
  emit('start')
}
function movePointer(event: PointerEvent) {
  if (pointer !== event.pointerId) return
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) release()
}
function pressKey(event: KeyboardEvent) {
  if (![' ', 'Enter'].includes(event.key)) return
  event.preventDefault()
  if (event.repeat || props.disabled || held.value) return
  key = event.key
  held.value = true
  emit('start')
}
watch(() => props.cancel, value => { if (value) release() })
onUnmounted(release)
</script>

<template>
  <Button
    type="button" variant="ghost" :disabled="disabled && !held"
    :aria-label="label" :aria-pressed="held" aria-describedby="manual-connection-status"
    :data-held="held" class="touch-none select-none"
    @pointerdown="pressPointer" @pointermove="movePointer"
    @pointerup="release" @pointercancel="release" @lostpointercapture="release" @pointerleave="release"
    @keydown="pressKey" @keyup="(event: KeyboardEvent) => { if (event.key === key) release() }" @blur="release"
    @contextmenu.prevent @click.prevent
  >
    <slot />
  </Button>
</template>
