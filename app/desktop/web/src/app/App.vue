<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogTitle } from '@/components/ui/dialog'
import { WorkspacePage } from '../features/workspace'
import { ManualControlPanel } from '../features/manual'
import { PreviewPanel } from '../features/preview'
import { SettingsPanel } from '../features/settings'
import { useControllerConnection } from '../connection/client'
import { loadSystemInfo } from '../connection/system-info'

const { state, error, start, stop, chooseProgram, startCycle, emergencyStop, resetEmergencyStop, setMachineControl, setSpindle, homeAll, submittingHome, axisProfiles } = useControllerConnection()
const message = ref('')
const showMessage = ref(false)
const confirmReset = ref(false)
const resetPending = ref(false)
const canReset = computed(() => state.value.canEstop && state.value.estop === true)
watch(canReset, allowed => { if (!allowed) confirmReset.value = false }, { flush: 'sync' })
const sendingStart = ref(false)
const applicationVersion = __ARCNOS_VERSION__
const adminSudo = window.cncAdminSudo
const terminal = window.cncTerminal
const TerminalPanel = defineAsyncComponent(() => import('../features/terminal').then(module => module.TerminalPanel))
const terminalKey = 'betterlinuxcnc.terminal.enabled'
const terminalEnabled = ref(false)
try { terminalEnabled.value = localStorage.getItem(terminalKey) === 'true' } catch { /* Use the session default. */ }
terminal?.setEnabled(terminalEnabled.value)

function setTerminalEnabled(enabled: boolean) {
  terminal?.setEnabled(enabled)
  terminalEnabled.value = enabled
  try { localStorage.setItem(terminalKey, String(enabled)) } catch { /* Keep the current session preference. */ }
}

async function selectProgram() {
  try {
    await chooseProgram()
    showMessage.value = false
  } catch (problem) {
    showError(problem)
  }
}

async function launchCycle() {
  if (sendingStart.value) return
  sendingStart.value = true
  try {
    await startCycle()
  } catch (problem) {
    showError(problem)
  } finally {
    sendingStart.value = false
  }
}

function showError(problem: unknown) {
  const detail = problem instanceof Error ? problem.message : String(problem)
  message.value = detail.replace(/^(?:Error: )?Error invoking remote method '[^']+': (?:Error: )?/, '')
  showMessage.value = true
}

async function requestEmergencyStop(enabled: boolean) {
  if (enabled) {
    try { await emergencyStop() } catch (problem) { showError(problem) }
  } else if (canReset.value && !resetPending.value) {
    confirmReset.value = true
  }
}

async function confirmEmergencyStopReset() {
  if (!confirmReset.value || !canReset.value || resetPending.value) return
  confirmReset.value = false
  resetPending.value = true
  try { await resetEmergencyStop(true) }
  catch (problem) { showError(problem) }
  finally { resetPending.value = false }
}
</script>

<template>
  <WorkspacePage v-slot="{ activeSection }" :terminal-enabled="terminalEnabled" :start-disabled="sendingStart || (!!state.programFile && !state.canStartCycle)"
    :can-estop="state.canEstop" :estop="state.estop" :reset-pending="resetPending" @start-cycle="launchCycle" @set-emergency-stop="requestEmergencyStop" @section-change="stop">
    <PreviewPanel v-if="activeSection === 'preview'" :file="state.programFile" />
    <ManualControlPanel v-else-if="activeSection === 'control'" :state="state" :error="error" :profiles="axisProfiles" :submitting-home="submittingHome"
      @home="homeAll" @start="start" @stop="stop" @spindle="setSpindle" @flood="setMachineControl('flood', $event)" @feed="setMachineControl('feed', $event)" />
    <SettingsPanel v-else-if="activeSection === 'settings'" :version="applicationVersion" :load-info="loadSystemInfo" :admin-sudo="adminSudo" :terminal-enabled="terminalEnabled" @update:terminal-enabled="setTerminalEnabled" />
    <TerminalPanel v-else-if="activeSection === 'terminal' && terminalEnabled" :bridge="terminal" />
  </WorkspacePage>
  <Dialog v-model:open="confirmReset">
    <DialogContent class="sm:max-w-sm" :show-close-button="false">
      <DialogTitle>确认解除急停</DialogTitle>
      <DialogDescription>请确认机床无异常、急停原因已排除，人员已离开运动范围。</DialogDescription>
      <DialogFooter>
        <DialogClose as-child><Button type="button" variant="outline">取消</Button></DialogClose>
        <Button type="button" @click="confirmEmergencyStopReset">确认解除急停</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
  <Dialog v-model:open="showMessage" :modal="false">
    <DialogContent :aria-describedby="undefined" class="sm:max-w-sm">
      <DialogTitle>{{ message }}</DialogTitle>
      <Button v-if="state.connected && message === '请先选择加工程序'" @click="selectProgram">选择程序</Button>
      <DialogClose as-child><Button class="justify-self-end">确定</Button></DialogClose>
    </DialogContent>
  </Dialog>
</template>
