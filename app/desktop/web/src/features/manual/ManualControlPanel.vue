<script setup lang="ts">
// 手动控制页，包含机床概览、移动控制和轴配置入口。
// Manual Control page with the machine overview, jog controls, and axis configuration.
import { computed, onUnmounted, ref, watch, watchEffect } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { SidebarMenuButton } from '@/components/ui/sidebar'
import { jogAxes, type AxisCount, type AxisProfileBridge, type ControlState, type JogAxis, type JogDirection, type JogRequest } from '../../../bridge'
import AxisJogPad from './AxisJogPad.vue'
import { previewFiles } from './axis-preview'
import AxisConfigurationPanel from './AxisConfigurationPanel.vue'
import MachineStatusCards from './MachineStatusCards.vue'

const props = defineProps<{ state: ControlState; error: string; profiles?: AxisProfileBridge; submittingHome: boolean }>()
const emit = defineEmits<{ start: [request: JogRequest]; stop: []; home: [confirmed: true]; power: [enabled: boolean]; spindle: [direction: -1 | 0 | 1, rpm?: number]; flood: [enabled: boolean]; feed: [ratio: number] }>()
const showAxes = ref(false)
const showConfiguration = ref(false)
const browserPreview = !!previewFiles && !window.cncControl
const confirmHoming = ref(false)
watch(() => props.state.canHomeAll, () => { confirmHoming.value = false })
function confirmHome() {
  if (!confirmHoming.value || !props.state.canHomeAll || props.submittingHome) return
  confirmHoming.value = false
  emit('home', true)
}
const previewCount = ref<AxisCount>(5)
const previewAxes = ref<JogAxis[]>([])
watchEffect(async onCleanup => {
  if (!previewFiles || window.cncControl || props.profiles || showConfiguration.value) return
  let current = true
  onCleanup(() => { current = false })
  previewAxes.value = []
  try {
    const { values } = await previewFiles.read(previewCount.value)
    if (current) previewAxes.value = jogAxes.filter(axis => values.axes?.includes(axis))
  } catch {
    // Without a readable preset the browser has no axis layout to show.
  }
})
const displayedAxes = computed(() => {
  const active = props.state.activeAxes
  return active ? jogAxes.filter(axis => active.some(item => item.name === axis)) : previewAxes.value
})
const xy = computed(() => displayedAxes.value.filter(axis => axis === 'X' || axis === 'Y'))
const rotaryAxes = computed(() => displayedAxes.value.filter(axis => 'ABC'.includes(axis)))
const rotaryPads = computed(() => {
  const axes = rotaryAxes.value
  const pads = []
  for (let i = 0; i < axes.length; i += 2) {
    pads.push({ vertical: axes[i], horizontal: axes[i + 1], label: axes.slice(i, i + 2).join('') })
  }
  return pads
})
const linearFeed = 100
const rotaryFeed = 30
function start(axis: JogAxis, direction: JogDirection) {
  const limit = props.state.axes[axis]?.maxFeed
  if (limit && limit > 0) emit('start', { axis, direction, feedRate: Math.min(limit, 'ABC'.includes(axis) ? rotaryFeed : linearFeed) })
}
onUnmounted(() => emit('stop'))
</script>

<template>
  <div class="manual-page">
    <header class="control-header">
      <h1 id="manual-title">手动控制</h1>
    </header>
    <section class="control-card" :class="{ overview: !showAxes && !showConfiguration }" aria-labelledby="manual-title">
      <span id="manual-connection-status" class="sr-only">
        {{ state.reason || '按住点动，松开停止；未配置的轴不可用' }}
      </span>

      <div v-if="!showAxes && !showConfiguration" class="overview-controls">
        <MachineStatusCards :readings="state.readings" :axes="displayedAxes"
          @spindle="(direction, rpm) => emit('spindle', direction, rpm)" @flood="emit('flood', $event)" @feed="emit('feed', $event)" />
        <div class="overview-motion text-base font-semibold">
          <Card as="button" type="button" :disabled="!displayedAxes.length" @click="showAxes = true">
            <span>移动控制</span><ChevronRight class="size-5 shrink-0" aria-hidden="true" />
          </Card>
          <Card as="button" type="button" :disabled="!profiles && !previewFiles" @click="showConfiguration = true">
            <span>轴配置</span><ChevronRight class="size-5 shrink-0" aria-hidden="true" />
          </Card>
        </div>
      </div>
      <div v-else-if="showConfiguration" class="px-6 pt-5">
        <SidebarMenuButton type="button" variant="workspace" class="h-10 w-auto px-4" @click="showConfiguration = false">
          <ChevronLeft aria-hidden="true" />{{ showAxes ? '返回移动控制' : '返回控制面板' }}
        </SidebarMenuButton>
      </div>
      <div v-else class="flex flex-wrap gap-2 px-6 pt-5">
        <SidebarMenuButton type="button" variant="workspace" class="h-10 w-auto px-4" @click="showAxes = false">
          <ChevronLeft aria-hidden="true" />返回控制面板
        </SidebarMenuButton>
        <SidebarMenuButton v-if="profiles || previewFiles" type="button" variant="workspace" class="h-10 w-auto px-4" @click="showConfiguration = true">
          <span>轴配置</span><ChevronRight aria-hidden="true" />
        </SidebarMenuButton>
        <Dialog v-model:open="confirmHoming">
          <DialogTrigger as-child>
            <Button type="button" variant="outline" class="ml-auto" :disabled="submittingHome || (!state.canHomeAll && !browserPreview)">回零</Button>
          </DialogTrigger>
          <DialogContent class="sm:max-w-sm" :show-close-button="false">
            <DialogTitle>确认回零</DialogTitle>
            <DialogDescription>请确认各轴回零路径无遮挡，人员已离开运动范围。确认后，机床将自动使能并按配置顺序回零。</DialogDescription>
            <DialogFooter>
              <DialogClose as-child><Button type="button" variant="outline">取消</Button></DialogClose>
              <Button type="button" :disabled="!state.canHomeAll || submittingHome" @click="confirmHome">确认无遮挡并回零</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Button type="button" variant="outline" :disabled="!state.canSetPower || state.powered === null" @click="emit('power', !state.powered)">
          {{ state.powered ? '关闭使能' : '使能' }}
        </Button>
      </div>

      <AxisConfigurationPanel v-if="showConfiguration" :bridge="profiles" :readings="state.readings"
        :preview-count="previewFiles && !profiles ? previewCount : undefined" @preview-select="previewCount = $event" />
      <div v-else-if="!showAxes" class="flex min-w-0 items-center justify-center p-4">
        <img
          src="./five-axis-cnc.png"
          alt="五轴机床示意图"
          width="1269"
          height="1240"
          class="h-auto max-h-[60svh] max-w-full object-contain"
        />
      </div>
      <div v-else class="axis-modules" :class="{ 'linear-only': !rotaryPads.length }">
        <section v-if="xy.length" class="axis-module" aria-labelledby="xy-title">
          <h2 id="xy-title">{{ xy.join('') }}</h2>
          <AxisJogPad :label="xy.join('')" :vertical-axis="xy.includes('Y') ? 'Y' : 'X'" :horizontal-axis="xy.length === 2 ? 'X' : undefined" :state="state" @start="start" @stop="emit('stop')" />
        </section>

        <section v-if="displayedAxes.includes('Z')" class="axis-module" aria-labelledby="z-title">
          <h2 id="z-title">Z</h2>
          <AxisJogPad label="Z" vertical-axis="Z" :state="state" @start="start" @stop="emit('stop')" />
        </section>

        <section v-for="pad in rotaryPads" :key="pad.label" class="axis-module" :aria-label="pad.label + ' 旋转控制'">
          <h2>{{ pad.label }}</h2>
          <AxisJogPad :label="pad.label" :vertical-axis="pad.vertical" :horizontal-axis="pad.horizontal" :state="state" @start="start" @stop="emit('stop')" />
        </section>
      </div>
      <footer v-if="!showConfiguration && (error || state.error || (state.serviceConnected && state.reason))" class="jog-settings">
        <p v-if="error || state.error" role="alert" class="control-error">{{ error || state.error }}</p>
        <p v-else-if="state.serviceConnected && state.reason" role="status" class="control-reason">{{ state.reason }}</p>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.manual-page {
  min-height: 100svh;
  display: flex;
  flex-direction: column;
  padding: 18px 18px 18px 0;
}

.control-card {
  --control-radius: 32px;
  --control-border: 1px;
  flex: 1;
  display: flex;
  flex-direction: column;
  border: var(--control-border) solid rgb(255 255 255 / 90%);
  border-radius: var(--control-radius);
  background: #eff0f2;
  box-shadow: 0 12px 36px rgb(34 43 61 / 4%), inset 0 0 14px 3px rgb(255 255 255 / 85%);
  backdrop-filter: blur(24px) saturate(140%);
}

.control-header {
  padding: 12px 24px 22px;
}

.control-card.overview {
  --overview-inset: 6px;
  --readout-radius: calc(var(--control-radius) - var(--control-border) - var(--overview-inset));
  display: grid;
  grid-template-columns: min(40%, 308px) minmax(0, 1fr);
  grid-template-rows: 1fr;
  gap: 10px;
  padding: var(--overview-inset);
}
.overview-controls {
  display: grid;
  grid-template-rows: 1fr auto;
  gap: inherit;
}
.overview-motion {
  display: grid;
  grid-template-rows: repeat(2, minmax(6rem, 1fr));
  gap: inherit;
}
.overview > footer { grid-column: 1 / -1; }
@media (max-width: 640px) {
  .control-card.overview { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto; align-content: start; }
}

.control-header h1 { font-size: 18px; font-weight: 600; letter-spacing: -0.03em; }

.axis-modules {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(140px, 0.65fr) minmax(0, 1fr);
  align-content: center;
  padding: 32px 28px;
}

.axis-module {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  padding: 8px 12px;
}

.axis-module + .axis-module { border-left: 1px solid rgb(114 126 146 / 10%); }
@media (min-width: 801px) {
  .axis-modules.linear-only { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.axis-module h2 { font-size: 24px; font-weight: 500; letter-spacing: -0.04em; }

.jog-settings { display: flex; flex-wrap: wrap; align-items: center; gap: 18px 28px; padding: 20px 32px 28px; border-top: 1px solid rgb(114 126 146 / 8%); }
.control-error, .control-reason { flex-basis: 100%; font-size: 12px; }
.control-error { color: var(--destructive); }
.control-reason { color: var(--muted-foreground); }

@media (max-width: 800px) {
  .axis-modules { grid-template-columns: 1fr; padding: 32px 24px; gap: 28px; }
  .axis-module { gap: 20px; }
  .axis-module + .axis-module { border-left: 0; border-top: 1px solid rgb(114 126 146 / 10%); padding-top: 28px; }
}

@media (prefers-reduced-transparency: reduce) {
  .control-card { backdrop-filter: none; }
}

@media (max-width: 480px) {
  .control-header { padding-right: 18px; padding-left: 18px; }
  .axis-modules { padding-right: 12px; padding-left: 12px; }
  .axis-module { padding-right: 0; padding-left: 0; }
}
</style>
