<script setup lang="ts">
// 手动控制页的概览卡片，显示主轴、冷却系统、进给倍率和工件坐标。
// Manual Control overview cards for the spindle, coolant, feed override, and work coordinates.
import { computed, ref, watch } from 'vue'
import { Crosshair, Drill, Droplets, Gauge } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import type { JogAxis, MachineReadings } from '../../../bridge'

const props = defineProps<{ readings: MachineReadings | null; axes: readonly JogAxis[] }>()
const emit = defineEmits<{ spindle: [direction: -1 | 0 | 1, rpm?: number]; flood: [enabled: boolean]; feed: [ratio: number] }>()
const target = ref('')
watch(() => props.readings?.spindleTarget, (rpm) => { target.value = rpm == null ? '' : String(rpm) }, { immediate: true })
const rpm = computed(() => Number(target.value))
const validRpm = computed(() => Number.isFinite(rpm.value) && rpm.value > 0
  && (props.readings?.spindleMin == null || rpm.value >= props.readings.spindleMin)
  && (props.readings?.spindleMax == null || rpm.value <= props.readings.spindleMax))
const positioned = computed(() => props.axes.map(axis => {
  const value = props.readings?.position[axis]
  return { axis, value: value == null ? '-' : (Math.abs(value) < 0.0005 ? 0 : value).toFixed(3) }
}))
const draft = ref<number | null>(null)
const feed = computed(() => draft.value ?? (props.readings?.feedRatio != null ? Math.round(props.readings.feedRatio * 100) : null))
const spindleStatus = computed(() => {
  switch (props.readings?.spindleDirection) {
    case 0: return '已停止'
    case 1: return '正转'
    case -1: return '反转'
    default: return ''
  }
})
watch(() => props.readings?.canSetFeed, allowed => { if (!allowed) draft.value = null })
function commitFeed(event: Event) {
  const input = event.target as HTMLInputElement
  if (props.readings?.canSetFeed) emit('feed', input.valueAsNumber / 100)
  draft.value = null
  if (feed.value !== null) input.value = String(feed.value)
}
</script>

<template>
  <div class="machine-readouts">
    <Card as="section">
      <div class="flex items-center gap-3">
        <Drill class="status-icon" aria-hidden="true" />
        <h2 class="flex-1">主轴</h2>
        <span v-if="spindleStatus" class="detail">{{ spindleStatus }}</span>
      </div>
      <p class="reading" aria-label="主轴反馈转速">{{ readings?.spindleRpm == null ? '-' : Math.round(readings.spindleRpm) }} <span class="text-muted-foreground">RPM</span></p>
      <div class="mt-2 flex flex-wrap items-center gap-2">
        <label class="flex items-center gap-1 text-sm">
          目标 RPM
          <input type="number" step="any" placeholder="-" :min="readings?.spindleMin ?? 0" :max="readings?.spindleMax ?? undefined" :disabled="!readings?.canForward && !readings?.canReverse"
            :value="target" @input="target = ($event.target as HTMLInputElement).value" class="w-20 rounded-md border px-2 py-1" />
        </label>
        <Button type="button" variant="outline" size="sm" :disabled="!readings?.canForward || !validRpm" @click="emit('spindle', 1, rpm)">正转</Button>
        <Button type="button" variant="outline" size="sm" :disabled="!readings?.canReverse || !validRpm" @click="emit('spindle', -1, rpm)">反转</Button>
        <Button type="button" variant="outline" size="sm" :disabled="!readings?.canStopSpindle" @click="emit('spindle', 0)">停止主轴</Button>
      </div>
      <div class="mt-3 flex items-center gap-3 border-t border-border/60 pt-3">
        <Droplets class="status-icon" aria-hidden="true" />
        <h2 class="flex-1">冷却系统</h2>
        <span v-if="readings?.flood == null" class="detail">-</span>
        <Switch aria-label="冷却系统" :model-value="readings?.flood === true" :disabled="!readings?.canSetFlood || readings.flood == null" @update:model-value="emit('flood', $event)" />
      </div>
      <div class="mt-3 flex items-center gap-3 border-t border-border/60 pt-3">
        <Gauge class="status-icon" aria-hidden="true" />
        <h2 class="flex-1">进给倍率</h2>
        <span class="font-medium tabular-nums">{{ feed ?? '-' }} %</span>
      </div>
      <input type="range" aria-label="进给倍率" aria-description="以百分比调整进给倍率"
        class="mt-3 block w-full accent-primary disabled:opacity-45" min="0" step="1"
        :max="readings?.feedMax == null ? undefined : Math.floor(readings.feedMax * 100)"
        :value="feed ?? 0" :aria-valuetext="feed == null ? '-' : feed + '%'" :disabled="!readings?.canSetFeed || feed == null || readings.feedMax == null"
        @input="draft = ($event.target as HTMLInputElement).valueAsNumber" @change="commitFeed" @pointercancel="draft = null" />
    </Card>
    <Card as="section" class="flex flex-col">
      <div class="flex items-center gap-3">
        <Crosshair class="status-icon" aria-hidden="true" />
        <h2>工件坐标<span v-if="readings?.workSystem"> · {{ readings.workSystem }}</span></h2>
      </div>
      <p v-if="!positioned.length" class="mt-2 text-muted-foreground">-</p>
      <dl v-else class="mt-2 flex flex-1 flex-col justify-center">
        <div v-for="{ axis, value } in positioned" :key="axis" class="flex max-h-14 flex-1 items-center justify-between py-1">
          <dt class="text-xl">{{ axis }}</dt>
          <dd class="text-2xl font-medium tabular-nums">{{ value }} <small class="text-sm text-muted-foreground">{{ 'ABC'.includes(axis) ? '°' : 'mm' }}</small></dd>
        </div>
      </dl>
    </Card>
  </div>
</template>

<style scoped>
.machine-readouts { display: grid; grid-template-rows: auto 1fr; gap: 10px; }
.machine-readouts h2 { font-size: 14px; font-weight: 600; }
.machine-readouts dl > div { border-block: none; }
.status-icon { width: 18px; height: 18px; color: var(--muted-foreground); stroke-width: 1.75; }
.detail { color: var(--muted-foreground); font-size: 12px; }
.reading { margin-top: 5px; font-size: 22px; font-variant-numeric: tabular-nums; white-space: nowrap; }
</style>
