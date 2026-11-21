<script setup lang="ts">
// Developer settings for the local administrator account.
// 开发者选项：在机床桌面首次设密，并切换 cnc_admin 的 sudo 权限。
import { onMounted, ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import { maintenanceRequiredMessage, type AdminSudoBridge } from '../../../bridge'

const props = defineProps<{ bridge?: AdminSudoBridge }>()
const enabled = ref<boolean | null>(null)
const maintenance = ref<boolean | null>(null)
const titles = {
  'maintenance-on': '启用 cnc-maint 运维账户',
  'maintenance-off': '关闭 cnc-maint 运维账户',
  blocked: maintenanceRequiredMessage,
  enroll: '设置 cnc_admin 密码', enable: '开启 sudo', disable: '关闭 sudo',
}
const mode = ref<keyof typeof titles | null>(null)
const busy = ref(false)
const error = ref('')
const maintenancePassword = ref('')
const password = ref('')
const confirmation = ref('')

function close() {
  mode.value = null
  maintenancePassword.value = password.value = confirmation.value = ''
}

async function refresh() {
  if (!props.bridge) return
  ;[maintenance.value, enabled.value] = await Promise.all([
    props.bridge.maintenanceStatus().catch(() => null), props.bridge.status().catch(() => null),
  ])
}
onMounted(refresh)

async function edit(target: boolean) {
  if (!props.bridge || busy.value) return
  busy.value = true
  error.value = ''
  try {
    maintenance.value = await props.bridge.maintenanceStatus()
    if (!maintenance.value) { mode.value = 'blocked'; return }
    mode.value = target ? (await props.bridge.needsSetup() ? 'enroll' : 'enable') : 'disable'
  } catch (problem) {
    if (problem instanceof Error && problem.message.includes(maintenanceRequiredMessage)) mode.value = 'blocked'
    error.value = '无法读取管理员状态'
    await refresh()
  } finally { busy.value = false }
}

async function submit() {
  if (!props.bridge || !mode.value || mode.value === 'blocked' || busy.value) return
  error.value = ''
  if ((mode.value === 'enroll' || mode.value === 'maintenance-on') && password.value !== confirmation.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  busy.value = true
  try {
    if (mode.value === 'maintenance-on' || mode.value === 'maintenance-off') {
      maintenance.value = await props.bridge.setMaintenanceEnabled(mode.value === 'maintenance-on', password.value)
      close()
      await refresh()
      return
    }
    enabled.value = mode.value === 'enroll'
      ? await props.bridge.enroll(maintenancePassword.value, password.value)
      : await props.bridge.setEnabled(mode.value === 'enable', password.value)
    close()
  } catch (problem) {
    error.value = problem instanceof Error ? problem.message : '无法确认管理员 sudo 状态'
    maintenancePassword.value = password.value = confirmation.value = ''
    await refresh()
    if (mode.value === 'maintenance-on' || mode.value === 'maintenance-off') {
      if (maintenance.value === (mode.value === 'maintenance-on')) close()
    } else if (maintenance.value === false) {
      mode.value = 'blocked'
    } else if (enabled.value === null || enabled.value === (mode.value !== 'disable')) {
      close()
    } else if (mode.value === 'enroll' && await props.bridge.needsSetup().catch(() => null) === false) {
      mode.value = 'enable'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="flex items-center justify-between gap-4 py-2">
    <span>cnc-maint 运维账户</span>
    <Switch v-if="maintenance !== null || !bridge" aria-label="cnc-maint 运维账户" :model-value="maintenance === true" :disabled="busy || !bridge"
      @update:model-value="target => { error = ''; mode = target ? 'maintenance-on' : 'maintenance-off' }" />
    <Button v-else variant="ghost" size="sm" @click="refresh">刷新状态</Button>
  </div>
  <div class="flex items-center justify-between gap-4 py-2">
    <span>cnc_admin 超管权限</span>
    <Switch v-if="enabled !== null || maintenance === false" aria-label="cnc_admin sudo" :model-value="enabled === true && maintenance === true" :disabled="busy"
      @update:model-value="edit" />
    <Button v-else-if="bridge" variant="ghost" size="sm" @click="refresh">刷新状态</Button>
    <span v-else class="text-muted-foreground">-</span>
  </div>
  <p v-if="error && !mode" role="alert" class="mt-2 text-sm text-destructive">{{ error }}</p>
  <Dialog :open="mode !== null" @update:open="open => { if (!open && !busy) { close(); error = '' } }">
    <DialogContent :aria-describedby="undefined" class="sm:max-w-sm">
      <DialogTitle>{{ mode ? titles[mode] : '' }}</DialogTitle>
      <Button v-if="mode === 'blocked'" @click="close">确定</Button>
      <form v-else class="grid gap-4" @submit.prevent="submit">
        <label v-if="mode === 'enroll'" class="grid gap-1.5">cnc-maint 运维密码
          <input v-model="maintenancePassword" required type="password" autocomplete="current-password" class="rounded-md border bg-background px-3 py-2" />
        </label>
        <label class="grid gap-1.5">{{ mode === 'maintenance-on' ? '设置运维密码' : mode === 'maintenance-off' ? '当前运维密码' : mode === 'enroll' ? '设置新密码' : '管理员密码' }}
          <input v-model="password" required type="password" :autocomplete="mode === 'enroll' || mode === 'maintenance-on' ? 'new-password' : 'current-password'" class="rounded-md border bg-background px-3 py-2" />
        </label>
        <label v-if="mode === 'enroll' || mode === 'maintenance-on'" class="grid gap-1.5">确认新密码
          <input v-model="confirmation" required type="password" autocomplete="new-password" class="rounded-md border bg-background px-3 py-2" />
        </label>
        <p v-if="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
        <Button type="submit" :disabled="busy">{{ mode === 'enroll' || mode === 'maintenance-on' ? '设置密码并开启' : '确认' }}</Button>
      </form>
    </DialogContent>
  </Dialog>
</template>
