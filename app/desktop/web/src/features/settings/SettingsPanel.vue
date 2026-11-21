<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Cpu, Monitor, MemoryStick, Terminal } from '@lucide/vue'
import { Switch } from '@/components/ui/switch'
import { Card } from '@/components/ui/card'
import type { AdminSudoBridge, SystemInfo } from '../../../bridge'
import AdminSudoSettings from './AdminSudoSettings.vue'

const props = defineProps<{ version: string; loadInfo: () => Promise<SystemInfo>; adminSudo?: AdminSudoBridge; terminalEnabled: boolean }>()
const emit = defineEmits<{ 'update:terminalEnabled': [enabled: boolean] }>()
const snapshot = ref<SystemInfo | null>(null)
const loading = ref(false)
let active = false
let timer: ReturnType<typeof setTimeout> | undefined
const gib = (bytes: number) => `${(bytes / 1024 ** 3).toFixed(1)} GiB`
const rows = computed(() => {
  const info = snapshot.value
  return [
    { label: 'CPU', icon: Cpu, value: info?.cpu?.model || '-' },
    { label: 'GPU', icon: Monitor, value: info?.gpus?.map(gpu => gpu.model).join(' / ') || '-' },
    { label: '内存', icon: MemoryStick, value: info?.memory ? gib(info.memory.totalBytes) : '-' },
    { label: 'Linux 内核', icon: Terminal, value: info?.kernel || '-' },
  ]
})

async function refresh() {
  if (loading.value) return
  if (timer) clearTimeout(timer)
  loading.value = true
  try {
    const result = await props.loadInfo()
    if (active) snapshot.value = result
  } catch {
    if (active) snapshot.value = null
  } finally {
    if (active) {
      loading.value = false
      timer = setTimeout(() => {
        if (document.visibilityState === 'visible') void refresh()
      }, 10000)
    }
  }
}
function visible() { if (document.visibilityState === 'visible') void refresh() }
onMounted(() => { active = true; void refresh(); document.addEventListener('visibilitychange', visible) })
onUnmounted(() => { active = false; if (timer) clearTimeout(timer); document.removeEventListener('visibilitychange', visible) })
</script>

<template>
  <section aria-label="系统设置" class="flex min-h-svh flex-col items-center px-6 pb-8 pt-[12svh]">
    <h1 class="select-none text-[clamp(3rem,14vw,12rem)] font-semibold leading-none tracking-[-0.06em] text-black">ArcnOS</h1>
    <p class="mt-4 text-lg tabular-nums tracking-wide text-black" aria-label="系统版本">{{ version }}</p>
    <div class="mt-10 w-full max-w-5xl" :aria-busy="loading">
      <Card as="article" aria-label="系统信息">
        <dl class="divide-y divide-border/60">
          <div v-for="row in rows" :key="row.label" role="group" :aria-label="row.label" class="flex items-center justify-between gap-6 py-4">
            <dt class="flex shrink-0 items-center gap-3 text-sm text-muted-foreground">
              <component :is="row.icon" class="size-4" aria-hidden="true" />
              {{ row.label }}
            </dt>
            <dd class="min-w-0 break-words text-right text-base font-medium text-card-foreground">{{ row.value }}</dd>
          </div>
        </dl>
      </Card>
      <section aria-label="开发者选项" class="mt-6">
        <h2 class="mb-2 px-2 text-base font-semibold">开发者选项</h2>
        <Card>
          <AdminSudoSettings :bridge="adminSudo" />
          <div class="flex items-center justify-between gap-4 py-2">
            <span>启用终端</span>
            <Switch aria-label="启用终端" :model-value="terminalEnabled" @update:model-value="emit('update:terminalEnabled', $event)" />
          </div>
        </Card>
      </section>
    </div>
  </section>
</template>
