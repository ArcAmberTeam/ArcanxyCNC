<script setup lang="ts">
// Developer settings for the local administrator account.
// 开发者选项：在机床桌面首次设密，并切换 cnc_admin 的 sudo 权限。
import { onMounted, ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import type { AdminSudoBridge } from '../../../bridge'

const props = defineProps<{ bridge?: AdminSudoBridge }>()
const enabled = ref<boolean | null>(null)
const mode = ref<'enroll' | 'enable' | 'disable' | null>(null)
const busy = ref(false)
const error = ref('')
const code = ref('')
const password = ref('')
const confirmation = ref('')

function close() {
  mode.value = null
  code.value = password.value = confirmation.value = ''
}

async function refresh() {
  if (!props.bridge) return
  enabled.value = await props.bridge.status().catch(() => null)
}
onMounted(refresh)

async function edit(target: boolean) {
  if (!props.bridge || busy.value) return
  busy.value = true
  error.value = ''
  try {
    mode.value = target ? (await props.bridge.needsSetup() ? 'enroll' : 'enable') : 'disable'
  } catch {
    error.value = '无法读取管理员状态'
    await refresh()
  } finally { busy.value = false }
}

async function submit() {
  if (!props.bridge || !mode.value || busy.value) return
  error.value = ''
  if (mode.value === 'enroll' && password.value !== confirmation.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  busy.value = true
  try {
    enabled.value = mode.value === 'enroll'
      ? await props.bridge.enroll(code.value.trim(), password.value)
      : await props.bridge.setEnabled(mode.value === 'enable', password.value)
    close()
  } catch (problem) {
    error.value = problem instanceof Error ? problem.message : '无法确认管理员 sudo 状态'
    password.value = confirmation.value = ''
    await refresh()
    if (enabled.value === null || enabled.value === (mode.value !== 'disable')) {
      close()
    } else if (mode.value === 'enroll' && await props.bridge.needsSetup().catch(() => null) === false) {
      code.value = ''
      mode.value = 'enable'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section aria-label="开发者选项" class="mt-6">
    <h2 class="mb-2 px-2 text-base font-semibold">开发者选项</h2>
    <Card class="flex items-center justify-between gap-4">
      <span>cnc_admin 超管权限</span>
      <Switch v-if="enabled !== null" aria-label="cnc_admin sudo" :model-value="enabled" :disabled="busy"
        @update:model-value="edit" />
      <Button v-else-if="bridge" variant="ghost" size="sm" @click="refresh">刷新状态</Button>
      <span v-else class="text-muted-foreground">-</span>
    </Card>
    <p v-if="error && !mode" role="alert" class="mt-2 text-sm text-destructive">{{ error }}</p>
    <Dialog :open="mode !== null" @update:open="open => { if (!open && !busy) { close(); error = '' } }">
      <DialogContent :aria-describedby="undefined" class="sm:max-w-sm">
        <DialogTitle>{{ mode === 'enroll' ? '首次开通 cnc_admin' : mode === 'enable' ? '开启 sudo' : '关闭 sudo' }}</DialogTitle>
        <form class="grid gap-4" @submit.prevent="submit">
          <label v-if="mode === 'enroll'" class="grid gap-1.5">一次性开通码
            <input v-model="code" required maxlength="39" autocomplete="one-time-code" spellcheck="false" class="rounded-md border bg-background px-3 py-2 font-mono" />
          </label>
          <label class="grid gap-1.5">{{ mode === 'enroll' ? '设置新密码' : '管理员密码' }}
            <input v-model="password" required type="password" :autocomplete="mode === 'enroll' ? 'new-password' : 'current-password'" class="rounded-md border bg-background px-3 py-2" />
          </label>
          <label v-if="mode === 'enroll'" class="grid gap-1.5">确认新密码
            <input v-model="confirmation" required type="password" autocomplete="new-password" class="rounded-md border bg-background px-3 py-2" />
          </label>
          <p v-if="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
          <Button type="submit" :disabled="busy">{{ mode === 'enroll' ? '设置密码并开启' : '确认' }}</Button>
        </form>
      </DialogContent>
    </Dialog>
  </section>
</template>
