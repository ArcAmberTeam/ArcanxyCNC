<script setup lang="ts">
// Axis parameter form backed by the selected INI document.
import { computed, ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { profileLayouts, type AxisCount, type AxisParameterFiles, type MachineReadings } from '../../../bridge'
import AxisConfigSelect from './AxisConfigSelect.vue'
import AxisParameterInput from './AxisParameterInput.vue'
import { axisFields, estimatedTravel, geometryFields, measuredTravel, motionFields, rtcpModels } from './axis-parameter-fields'

const props = defineProps<{ count: AxisCount; bridge: AxisParameterFiles; readings?: MachineReadings | null; busy?: boolean }>()
const emit = defineEmits<{ saving: [value: boolean] }>()
const revision = ref('')
const baseline = ref<Record<string, string>>({})
const loading = ref(false)
const writing = ref(false)
const values = ref<Record<string, string>>({})
const message = ref('')
const problem = ref('')

watch(() => props.count, async (count, _, onCleanup) => {
  let live = true
  onCleanup(() => { live = false })
  message.value = ''
  problem.value = ''
  values.value = {}
  revision.value = ''
  loading.value = true
  try {
    const doc = await props.bridge.read(count)
    if (!live) return
    baseline.value = doc.values
    values.value = { ...doc.values }
    revision.value = doc.revision
  } catch (error) {
    if (live) problem.value = error instanceof Error ? error.message : String(error)
  } finally { if (live) loading.value = false }
}, { immediate: true })

const model = computed(() => props.count === 5 ? values.value.model || '' : '')
const modelChoices = [
  { value: '', label: '-' },
  { value: 'trivkins', label: '常规五轴', detail: 'trivkins' },
  ...rtcpModels.map(item => ({ value: item.value, label: item.label + ' RTCP', detail: item.value })),
]
const layout = computed(() => values.value.axes || profileLayouts[props.count])
const rows = computed(() => [...layout.value].map(name => {
  const rotary = 'ABC'.includes(name)
  return { name, unit: rotary ? '°' : 'mm', fields: axisFields(rotary) }
}))
const travelFields = computed(() => rows.value.some(row => (row.name + '.estimatedTravel') in baseline.value)
  ? [estimatedTravel, measuredTravel] : [measuredTravel])
const liveGeometry = computed(() => props.readings?.rtcpModel === model.value ? props.readings.rtcpGeometry : {})
const geometry = computed(() => geometryFields(model.value).filter(field =>
  (model.value + '.' + field.key) in baseline.value || liveGeometry.value[field.key] != null))
function value(key: string) { return values.value[key] ?? '' }
function edit(key: string, text: string) {
  values.value[key] = text
  message.value = ''
  problem.value = ''
}
async function save(event: SubmitEvent) {
  message.value = ''
  problem.value = ''
  if (props.busy || loading.value || writing.value || (!props.bridge.save || !revision.value)) return
  const form = event.currentTarget as HTMLFormElement
  for (const input of form.querySelectorAll<HTMLInputElement>('input')) {
    if (!input.validity.valid || (input.dataset.positive && input.value !== '' && input.valueAsNumber <= 0)) {
      input.closest('details')?.setAttribute('open', '')
      input.focus()
      problem.value = input.getAttribute('aria-label') + '的数值无效'
      return
    }
  }
  for (const row of rows.value) {
    for (const [low, high, label] of [['min', 'max', '软限位'], ['angleMin', 'angleMax', '机械转角']]) {
      const lower = value(row.name + '.' + low)
      const upper = value(row.name + '.' + high)
      if (lower && upper && Number(lower) >= Number(upper)) {
        problem.value = row.name + ' 轴' + label + '下限必须小于上限'
        return
      }
    }
  }
  const changes = Object.fromEntries(Object.entries(values.value).filter(([key, val]) => val !== (baseline.value[key] ?? '')))
  writing.value = true
  emit('saving', true)
  try {
    const doc = await props.bridge.save(props.count, revision.value, changes)
    baseline.value = doc.values
    values.value = { ...doc.values }
    revision.value = doc.revision
    message.value = '轴参数已保存'
  } catch (error) {
    problem.value = error instanceof Error ? error.message : String(error)
  } finally { writing.value = false; emit('saving', false) }
}
</script>

<template>
  <form class="grid min-w-0 gap-4" aria-label="轴参数配置" novalidate @submit.prevent="save">
    <fieldset v-if="revision" class="grid min-w-0 gap-4" :disabled="busy || loading || writing || !bridge.save">
      <AxisConfigSelect v-if="count === 5" label="运动学模型" :model-value="model" :choices="modelChoices.filter(c => c.value === model).map(c => ({ ...c, disabled: true }))"
        @update:model-value="edit('model', $event)" />
      <Card as="section" aria-labelledby="axis-parameters-caption" class="min-w-0">
        <div class="overflow-x-auto">
          <table class="w-full min-w-[32rem] table-fixed text-left text-sm">
            <caption id="axis-parameters-caption" class="pb-2 text-left font-semibold">轴参数</caption>
            <thead><tr>
              <th scope="col" class="w-8">轴</th>
              <th v-for="field in travelFields" :key="field.key" scope="col" class="px-1 py-2">{{ field.label }}</th>
              <th v-for="field in motionFields" :key="field.key" scope="col" class="px-1 py-2">{{ field.label }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="row in rows" :key="row.name">
                <th scope="row">{{ row.name }}</th>
                <td v-for="field in travelFields" :key="field.key" class="px-1 py-1">
                  <AxisParameterInput :field="field" :name="row.name + '.' + field.key" :label="row.name + ' ' + field.label"
                    :unit="row.unit" :value="value(row.name + '.' + field.key)"
                    @change="edit(row.name + '.' + field.key, $event)" />
                </td>
                <td v-for="field in motionFields" :key="field.key" class="px-1 py-1">
                  <AxisParameterInput :field="field" :name="row.name + '.' + field.key" :label="row.name + ' ' + field.label"
                    :unit="row.unit + (field.key === 'maxFeed' ? '/min' : '')" :value="value(row.name + '.' + field.key)"
                    @change="edit(row.name + '.' + field.key, $event)" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <details v-for="row in rows" :key="row.name" class="text-sm">
          <summary class="cursor-pointer py-3 font-medium">{{ row.name }} 轴传动与回零</summary>
          <div class="grid gap-3 pb-4 sm:grid-cols-2">
            <div v-for="field in row.fields" :key="field.key" class="grid gap-1">
              <span>{{ field.label }}</span>
              <AxisParameterInput :field="field" :name="row.name + '.' + field.key" :label="row.name + ' ' + field.label"
                :disabled="field.key === 'joint' || field.key === 'drive'" :value="value(row.name + '.' + field.key)" @change="edit(row.name + '.' + field.key, $event)" />
            </div>
            <label class="grid gap-1">{{ row.unit === '°' ? '正转方向' : '运动方向' }}
              <select :aria-label="row.name + (row.unit === '°' ? ' 正转方向' : ' 运动方向')" :value="value(row.name + '.direction')" class="parameter-select"
                @change="edit(row.name + '.direction', ($event.target as HTMLSelectElement).value)">
                <option value="">-</option><option value="positive">正向</option><option value="negative">反向</option>
              </select>
            </label>
            <label class="grid gap-1">回零方式
              <select disabled :aria-label="row.name + ' 回零方式'" :value="value(row.name + '.homing')" class="parameter-select"
                @change="edit(row.name + '.homing', ($event.target as HTMLSelectElement).value)">
                <option value="">-</option><option value="manual">手动对零</option><option value="switch">原点开关</option>
                <option value="index">编码器索引</option><option value="switch-index">原点开关与编码器索引</option>
                <option value="absolute">绝对编码器</option>
              </select>
            </label>
          </div>
        </details>
      </Card>
      <Card v-if="geometry.length" class="min-w-0">
        <fieldset class="grid min-w-0 gap-3 text-sm sm:grid-cols-2">
          <legend class="pb-2 font-medium">RTCP 几何参数</legend>
          <div v-for="field in geometry" :key="field.key" class="grid gap-1">
            <span>{{ field.label }}</span>
            <output v-if="!((model + '.' + field.key) in baseline)">{{ liveGeometry[field.key] }} mm</output>
            <AxisParameterInput v-else :field="field" :name="model + '.' + field.key" :label="field.label"
              :value="value(model + '.' + field.key)" @change="edit(model + '.' + field.key, $event)" />
          </div>
        </fieldset>
      </Card>
      <div class="flex flex-wrap items-center gap-3">
        <Button v-if="bridge.save" type="submit">保存参数</Button>
        <p v-if="message" role="status" class="text-sm">{{ message }}</p>
      </div>
    </fieldset>
    <p v-if="problem" role="alert" class="text-sm text-destructive">{{ problem }}</p>
  </form>
</template>

<style scoped>
.parameter-select { min-width: 0; width: 100%; height: 2.25rem; border: 1px solid var(--input); border-radius: .375rem; background: var(--background); padding-inline: .5rem; }
</style>
