<script setup lang="ts">
// 移动控制页的方向键组，用于点动一个或两个轴。
// Directional pad for jogging one or two axes on the Motion Control page.
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from '@lucide/vue'
import type { ControlState, JogAxis, JogDirection } from '../../../bridge'
import JogButton from './JogButton.vue'

const props = defineProps<{
  label: string
  verticalAxis: JogAxis
  horizontalAxis?: JogAxis
  state: ControlState
}>()
const emit = defineEmits<{ start: [axis: JogAxis, direction: JogDirection]; stop: [] }>()
function disabled(axis: JogAxis) {
  const config = props.state.axes[axis]
  return !props.state.canJog || !config || !Number.isFinite(config.maxFeed) || config.maxFeed <= 0
}
</script>

<template>
  <div class="jog-pad" :class="{ 'jog-pad-vertical': !horizontalAxis }" role="group" :aria-label="`${label} 轴点动`">
    <JogButton class="jog-key jog-up" :disabled="disabled(verticalAxis)" :cancel="!state.jogging" :label="`${verticalAxis} 轴正向`" @start="emit('start', verticalAxis, 1)" @stop="emit('stop')">
      <ChevronUp class="size-5" :stroke-width="1.7" aria-hidden="true" />
      <span>{{ verticalAxis }}+</span>
    </JogButton>
    <JogButton v-if="horizontalAxis" class="jog-key jog-left" :disabled="disabled(horizontalAxis)" :cancel="!state.jogging" :label="`${horizontalAxis} 轴负向`" @start="emit('start', horizontalAxis, -1)" @stop="emit('stop')">
      <ChevronLeft class="size-5" :stroke-width="1.7" aria-hidden="true" />
      <span>{{ horizontalAxis }}−</span>
    </JogButton>
    <div class="jog-center" aria-hidden="true">{{ label }}</div>
    <JogButton v-if="horizontalAxis" class="jog-key jog-right" :disabled="disabled(horizontalAxis)" :cancel="!state.jogging" :label="`${horizontalAxis} 轴正向`" @start="emit('start', horizontalAxis, 1)" @stop="emit('stop')">
      <ChevronRight class="size-5" :stroke-width="1.7" aria-hidden="true" />
      <span>{{ horizontalAxis }}+</span>
    </JogButton>
    <JogButton class="jog-key jog-down" :disabled="disabled(verticalAxis)" :cancel="!state.jogging" :label="`${verticalAxis} 轴负向`" @start="emit('start', verticalAxis, -1)" @stop="emit('stop')">
      <ChevronDown class="size-5" :stroke-width="1.7" aria-hidden="true" />
      <span>{{ verticalAxis }}−</span>
    </JogButton>
  </div>
</template>

<style scoped>
.jog-pad {
  --key-size: clamp(52px, 6vw, 76px);
  display: grid;
  grid-template-columns: repeat(3, var(--key-size));
  grid-template-rows: repeat(3, var(--key-size));
  gap: 10px;
  align-items: center;
  justify-items: center;
}

.jog-pad-vertical {
  grid-template-columns: var(--key-size);
}

.jog-key {
  width: var(--key-size);
  height: var(--key-size);
  padding: 0;
  flex-direction: column;
  gap: 3px;
  border: 1px solid rgb(255 255 255 / 90%);
  border-radius: 22px;
  background: linear-gradient(145deg, #fff, rgb(248 249 251 / 85%));
  color: #65666d;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 4px 10px rgb(35 43 58 / 4%), inset 0 1px 0 white;
}

.jog-key:disabled {
  opacity: 1;
}

.jog-key[data-held="true"] {
  color: var(--primary);
  background: #edf4ff;
  box-shadow: inset 0 2px 6px rgb(0 102 204 / 12%);
}

.jog-up { grid-area: 1 / 2; }
.jog-left { grid-area: 2 / 1; }
.jog-right { grid-area: 2 / 3; }
.jog-down { grid-area: 3 / 2; }
.jog-center {
  grid-area: 2 / 2;
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: rgb(228 231 237 / 35%);
  color: #8a8d96;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.jog-pad-vertical > * { grid-column: 1; }

@media (max-width: 480px) {
  .jog-pad { --key-size: 44px; gap: 8px; }
  .jog-key { border-radius: 16px; }
  .jog-center { width: 32px; height: 32px; }
}
</style>
