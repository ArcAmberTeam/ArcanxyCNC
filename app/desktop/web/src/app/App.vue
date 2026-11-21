<script setup lang="ts">
import { ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { WorkspacePage } from '../features/workspace'
import { ManualControlPanel } from '../features/manual'
import { PreviewPanel } from '../features/preview'
import { SettingsPanel } from '../features/settings'
import { useControllerConnection } from '../connection/client'
import { loadSystemInfo } from '../connection/system-info'

const { state, error, start, stop, chooseProgram, startCycle, emergencyStop, setMachineControl, setSpindle, axisProfiles } = useControllerConnection()
const startMessage = ref('')
const showMessage = ref(false)
const sendingStart = ref(false)
const applicationVersion = __ARCNOS_VERSION__
const adminSudo = window.cncAdminSudo

async function selectProgram() {
  try {
    await chooseProgram()
    showMessage.value = false
  } catch (problem) {
    startMessage.value = problem instanceof Error ? problem.message : String(problem)
  }
}

async function launchCycle() {
  if (sendingStart.value) return
  sendingStart.value = true
  try {
    await startCycle()
  } catch (problem) {
    startMessage.value = problem instanceof Error ? problem.message : String(problem)
    showMessage.value = true
  } finally {
    sendingStart.value = false
  }
}
</script>

<template>
  <WorkspacePage v-slot="{ activeSection }" :start-disabled="sendingStart || (!!state.programFile && !state.canStartCycle)" :can-estop="state.canEstop" @start-cycle="launchCycle" @emergency-stop="emergencyStop" @section-change="stop">
    <PreviewPanel v-if="activeSection === 'preview'" :file="state.programFile" />
    <ManualControlPanel v-else-if="activeSection === 'control'" :state="state" :error="error" :profiles="axisProfiles" @start="start" @stop="stop" @spindle="setSpindle" @flood="setMachineControl('flood', $event)" @feed="setMachineControl('feed', $event)" />
    <SettingsPanel v-else-if="activeSection === 'settings'" :version="applicationVersion" :load-info="loadSystemInfo" :admin-sudo="adminSudo" />
  </WorkspacePage>
  <Dialog v-model:open="showMessage" :modal="false">
    <DialogContent :aria-describedby="undefined" class="sm:max-w-sm">
      <DialogTitle>{{ startMessage }}</DialogTitle>
      <Button v-if="state.connected && startMessage === '请先选择加工程序'" @click="selectProgram">选择程序</Button>
      <DialogClose as-child><Button class="justify-self-end">确定</Button></DialogClose>
    </DialogContent>
  </Dialog>
</template>
