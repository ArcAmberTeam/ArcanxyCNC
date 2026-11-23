import { onMounted, onUnmounted, readonly, shallowRef } from 'vue'
import { offlineState, type ControlBridge, type JogRequest } from '../../bridge'

declare global {
  interface Window { cncControl?: ControlBridge }
}

export function useControllerConnection() {
  const state = shallowRef(offlineState('机床未连接'))
  const error = shallowRef('')
  const submittingHome = shallowRef(false)
  const bridge = window.cncControl
  let unsubscribe: (() => void) | undefined
  let timer: ReturnType<typeof setInterval> | undefined
  let mounted = false
  let received = false
  function stop() { bridge?.stopJog() }
  function heartbeat() {
    if (document.visibilityState === 'visible' && document.hasFocus()) bridge?.heartbeat()
  }
  function hidden() { if (document.visibilityState !== 'visible') stop() }
  async function start(request: JogRequest) {
    if (!bridge) return
    error.value = ''
    try { bridge.heartbeat(); await bridge.startJog(request) }
    catch (problem) { stop(); error.value = problem instanceof Error ? problem.message : String(problem) }
  }
  async function chooseProgram() {
    if (!bridge) throw new Error('请在机床桌面端选择加工程序')
    await bridge.chooseProgram()
  }
  async function startCycle() {
    if (!bridge || state.value.programFile === '') throw new Error('请先选择加工程序')
    if (!state.value.programFile) throw new Error('机床状态未知，请检查控制服务连接')
    bridge.heartbeat()
    await bridge.startCycle(state.value.programFile)
  }
  async function emergencyStop() {
    if (!bridge) throw new Error('控制服务未连接')
    await bridge.emergencyStop()
  }
  async function resetEmergencyStop(confirmed: true) {
    if (!bridge) throw new Error('控制服务未连接')
    bridge.heartbeat()
    await bridge.resetEmergencyStop(confirmed)
  }
  async function homeAll(confirmed: true) {
    if (!bridge || !state.value.canHomeAll || submittingHome.value) return
    submittingHome.value = true
    error.value = ''
    try { bridge.heartbeat(); await bridge.homeAll(confirmed) }
    catch (problem) { error.value = problem instanceof Error ? problem.message : String(problem) }
    finally { submittingHome.value = false }
  }
  async function setMachineControl(setting: 'flood' | 'feed', value: boolean | number) {
    if (!bridge) return
    error.value = ''
    try {
      bridge.heartbeat()
      if (setting === 'flood' && typeof value === 'boolean') await bridge.setFlood(value)
      if (setting === 'feed' && typeof value === 'number') await bridge.setFeedOverride(value)
    } catch (problem) { error.value = problem instanceof Error ? problem.message : String(problem) }
  }
  async function setSpindle(direction: -1 | 0 | 1, rpm?: number) {
    if (!bridge) return
    error.value = ''
    try { bridge.heartbeat(); await bridge.setSpindle(direction, rpm) }
    catch (problem) { error.value = problem instanceof Error ? problem.message : String(problem) }
  }
  onMounted(() => {
    mounted = true
    if (!bridge) return
    unsubscribe = bridge.onState(value => { received = true; state.value = value })
    void bridge.getState().then(value => { if (mounted && !received) state.value = value })
      .catch(problem => { if (mounted) error.value = String(problem) })
    window.addEventListener('blur', stop)
    window.addEventListener('pagehide', stop)
    document.addEventListener('visibilitychange', hidden)
    heartbeat()
    timer = setInterval(heartbeat, 100)
  })
  onUnmounted(() => {
    mounted = false
    stop()
    if (timer) clearInterval(timer)
    unsubscribe?.()
    window.removeEventListener('blur', stop)
    window.removeEventListener('pagehide', stop)
    document.removeEventListener('visibilitychange', hidden)
  })
  return { state: readonly(state), error: readonly(error), start, stop, chooseProgram, startCycle, emergencyStop, resetEmergencyStop,
    setMachineControl, setSpindle, homeAll, submittingHome: readonly(submittingHome), axisProfiles: window.cncAxisProfiles }
}
