<script setup lang="ts">
// Local administrator terminal in the main workspace.
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { maintenanceRequiredMessage, type TerminalBridge } from '../../../bridge'

const props = defineProps<{ bridge?: TerminalBridge }>()
const terminalBackground = '#000000'
const host = ref<HTMLDivElement>()
const status = ref(props.bridge ? '' : '终端未连接')
const maintenanceDialog = ref(false)
let screen: Terminal | undefined
let fit: FitAddon | undefined
let observer: ResizeObserver | undefined
let unsubscribe: (() => void) | undefined
let sessionId: string | undefined

async function connect() {
  const bridge = props.bridge
  if (!screen || !bridge || sessionId) return
  status.value = ''
  screen.reset()
  fit?.fit()
  const id = crypto.randomUUID()
  sessionId = id
  try {
    await bridge.open(id, screen.cols, screen.rows)
    if (sessionId === id) screen?.focus()
  } catch (error) {
    if (sessionId !== id) return
    sessionId = undefined
    const message = error instanceof Error ? error.message : ''
    maintenanceDialog.value = message.includes(maintenanceRequiredMessage)
    status.value = maintenanceDialog.value ? '运维账户未启用'
      : message.includes('linuxcnc 桌面') ? '请在机床的 linuxcnc 桌面登录终端' : '终端连接失败'
  }
}

onMounted(() => {
  const bridge = props.bridge
  if (!host.value || !bridge) return
  const terminal = new Terminal({
    cursorBlink: true, fontSize: 15, scrollback: 2000,
    fontFamily: 'ui-monospace, "DejaVu Sans Mono", monospace',
    theme: { background: terminalBackground, foreground: '#f0f0f1', cursor: '#f0f0f1' },
  })
  screen = terminal
  fit = new FitAddon()
  terminal.loadAddon(fit)
  terminal.open(host.value)
  terminal.onData(text => {
    if (!sessionId) return
    let offset = 0
    while (offset < text.length) {
      let end = Math.min(offset + 65536, text.length)
      const last = text.charCodeAt(end - 1)
      if (end < text.length && last >= 0xd800 && last <= 0xdbff) end--
      bridge.input(sessionId, text.slice(offset, end))
      offset = end
    }
  })
  terminal.onResize(({ cols, rows }) => { if (sessionId) bridge.resize(sessionId, cols, rows) })
  unsubscribe = bridge.onEvent(event => {
    if (event.id !== sessionId) return
    if (event.kind === 'data') {
      terminal.write(event.text, () => { if (sessionId === event.id) bridge.consumed(event.id, event.text.length) })
    } else {
      sessionId = undefined
      maintenanceDialog.value = event.maintenanceDisabled === true
      status.value = maintenanceDialog.value ? '运维账户未启用' : event.code === 0 ? '会话已结束' : '终端登录失败或会话已中断'
    }
  })
  observer = new ResizeObserver(() => fit?.fit())
  observer.observe(host.value)
  void connect()
})

onBeforeUnmount(() => {
  if (sessionId) props.bridge?.close(sessionId)
  sessionId = undefined
  unsubscribe?.()
  observer?.disconnect()
  screen?.dispose()
})
</script>

<template>
  <div class="terminal-workspace">
    <header class="terminal-header">
      <h1 class="flex items-center gap-2">终端 <span v-if="bridge" class="font-mono text-sm font-normal text-muted-foreground">cnc_admin</span></h1>
      <Button v-if="bridge && status" variant="ghost" size="sm" class="h-6" @click="connect">重新连接</Button>
    </header>
    <section aria-label="系统终端" class="terminal-panel">
      <div ref="host" class="min-h-0 min-w-0 flex-1" />
      <p v-if="status" role="status" class="pt-2 text-sm text-neutral-400">{{ status }}</p>
    </section>
    <Dialog v-model:open="maintenanceDialog">
      <DialogContent :aria-describedby="undefined" class="sm:max-w-sm">
        <DialogTitle>{{ maintenanceRequiredMessage }}</DialogTitle>
        <DialogClose as-child><Button>确定</Button></DialogClose>
      </DialogContent>
    </Dialog>
  </div>
</template>

<style scoped>
.terminal-workspace {
  display: flex;
  flex-direction: column;
  height: 100svh;
  padding: 18px 18px 18px 0;
}

.terminal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px 22px;
}

.terminal-header h1 { font-size: 18px; font-weight: 600; letter-spacing: -0.03em; }

.terminal-panel {
  flex: 1;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: clamp(12px, 2vw, 20px);
  overflow: hidden;
  border-radius: 32px;
  background-color: v-bind(terminalBackground);
  color: #f0f0f1;
}
</style>
