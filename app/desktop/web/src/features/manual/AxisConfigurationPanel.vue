<script setup lang="ts">
// 轴配置页，用于选择轴方案并将其应用到机床。
// Axis Configuration page for selecting an axis profile and applying it to the machine.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Button } from '@/components/ui/button'
import type { AxisCount, AxisProfileBridge, AxisProfileStatus, MachineReadings } from '../../../bridge'
import AxisConfigSelect from './AxisConfigSelect.vue'
import { previewFiles } from './axis-preview'
import AxisParameterForm from './AxisParameterForm.vue'

const props = defineProps<{ bridge?: AxisProfileBridge; readings: MachineReadings | null }>()
const files = computed(() => props.bridge ?? previewFiles)
const counts = [3, 4, 5] as const
const labels = { 3: '三轴', 4: '四轴', 5: '五轴' }
const status = ref<AxisProfileStatus | null>(null)
const selection = ref<AxisCount | null>(null)
const fetching = ref(false)
const submitting = ref(false)
const error = ref('')
const pending = computed(() => ['scheduled', 'switching'].includes(status.value?.operation?.phase ?? ''))
const saving = ref(false)
const reload = ref(0)
const choices = computed(() => counts.map(count => {
  const profile = status.value?.profiles.find(item => item.axis_count === count)
  return {
    value: count, label: labels[count], detail: profile?.axes ?? '',
    note: count === status.value?.configured_axis_count && selection.value !== count ? '已写入' : '',
    disabled: pending.value || submitting.value || fetching.value || saving.value || (!!props.bridge && !profile),
    description: profile && !profile.available ? profile.reason || '当前机床不支持此方案' : '',
  }
}))
const progress = computed(() => {
  const op = status.value?.operation
  if (!op) return ''
  const name = labels[op.axis_count]
  switch (op.phase) {
    case 'scheduled': return name + '方案已提交，等待切换。'
    case 'switching': return '正在切换到' + name + '方案。'
    case 'configured': return name + '方案已写入。'
    case 'error': return name + '方案切换失败。' + op.message
    case 'unconfirmed': return '尚未确认' + name + '方案的切换结果，请刷新状态。'
  }
})
let mounted = false
let trackOperation = false
let poll: ReturnType<typeof setTimeout> | undefined

async function refresh() {
  if (!props.bridge || fetching.value) return
  clearTimeout(poll)
  fetching.value = true
  try {
    const result = await props.bridge.status()
    if (!mounted) return
    status.value = result
    error.value = ''
    if (pending.value) selection.value = result.operation!.axis_count
    else if (selection.value === null || trackOperation || result.profiles.find(p => p.axis_count === selection.value)?.available)
      selection.value = result.configured_axis_count
    if (trackOperation && !pending.value) reload.value++
    trackOperation = pending.value
  } catch (problem) {
    if (!mounted) return
    status.value = null
    error.value = problem instanceof Error ? problem.message : String(problem)
  } finally {
    fetching.value = false
    if (mounted && trackOperation) poll = setTimeout(refresh, 2000)
  }
}
async function select(count: AxisCount) {
  if (saving.value || fetching.value || submitting.value || pending.value) return
  if (!props.bridge) { selection.value = count; return }
  const profile = status.value?.profiles.find(p => p.axis_count === count)
  if (!status.value || !profile) return
  selection.value = count
  if (!profile.available) { error.value = profile.reason; return }
  error.value = ''
  const current = status.value.selected_axis_count === undefined ? status.value.configured_axis_count : status.value.selected_axis_count
  if (count === current) return
  submitting.value = true
  try {
    const accepted = await props.bridge.request(count)
    if (!mounted) return
    status.value.operation = accepted
    trackOperation = true
    await refresh()
  } catch (problem) {
    if (!mounted) return
    selection.value = null
    await refresh()
    if (mounted) error.value = problem instanceof Error ? problem.message : String(problem)
  } finally { submitting.value = false }
}
onMounted(() => { mounted = true; void refresh() })
onUnmounted(() => { mounted = false; clearTimeout(poll) })
</script>

<template>
  <section class="mx-auto grid w-full max-w-3xl gap-5 px-5 py-5 sm:px-8" aria-labelledby="axis-config-title">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 id="axis-config-title" class="text-xl font-semibold">轴配置</h2>
      <Button v-if="bridge || previewFiles" type="button" variant="ghost" size="sm" :disabled="fetching || submitting || saving" @click="reload++; refresh()">刷新状态</Button>
    </div>
    <AxisConfigSelect v-if="files" :model-value="selection" label="轴方案" @update:model-value="select" :choices="choices" />
    <div v-if="bridge" class="grid gap-2">
      <p v-if="progress" role="status" class="text-sm" :class="{ 'text-destructive': status?.operation?.phase === 'error' }">{{ progress }}</p>
      <p v-if="error" role="alert" class="break-words text-sm text-destructive">{{ error }}</p>
    </div>
    <AxisParameterForm v-if="selection && files" :key="selection + '-' + reload" :count="selection"
      :bridge="files" :readings="status?.configured_axis_count === selection ? readings : null" :busy="pending || submitting || fetching || (!!bridge && !status)"
      @saving="saving = $event" />
  </section>
</template>
