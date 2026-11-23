import { contextBridge, ipcRenderer } from 'electron'
import type { AdminSudoBridge, AxisProfileBridge, ControlBridge, ControlState, JogRequest, SystemBridge, TerminalBridge, TerminalEvent } from '../bridge.js' with { "resolution-mode": "import" }

const stateListeners = new Set<(state: ControlState) => void>()
ipcRenderer.on('control:state', (_event, id: number, state: ControlState) => {
  try { stateListeners.forEach(listener => listener(state)) }
  finally { ipcRenderer.send('control:state-consumed', id) }
})
const bridge: ControlBridge = {
  getState: () => ipcRenderer.invoke('control:state'),
  homeAll: confirmed => ipcRenderer.invoke('control:home-all', confirmed),
  setFlood: enabled => ipcRenderer.invoke('control:flood', enabled),
  setSpindle: (direction, rpm) => ipcRenderer.invoke('control:spindle', direction, rpm),
  setFeedOverride: ratio => ipcRenderer.invoke('control:feed', ratio),
  startJog: (request: JogRequest) => ipcRenderer.invoke('control:start', request),
  stopJog: () => ipcRenderer.send('control:stop'),
  chooseProgram: () => ipcRenderer.invoke('control:choose-program'),
  startCycle: file => ipcRenderer.invoke('control:cycle', file),
  emergencyStop: () => ipcRenderer.invoke('control:estop'),
  resetEmergencyStop: () => ipcRenderer.invoke('control:estop-reset'),
  heartbeat: () => ipcRenderer.send('control:heartbeat'),
  onState(callback: (state: ControlState) => void) {
    stateListeners.add(callback)
    return () => { stateListeners.delete(callback) }
  },
}
contextBridge.exposeInMainWorld('cncControl', bridge)
const systemBridge: SystemBridge = { getInfo: () => ipcRenderer.invoke('system:info') }
contextBridge.exposeInMainWorld('cncSystem', systemBridge)
const adminSudo: AdminSudoBridge = {
  maintenanceStatus: () => ipcRenderer.invoke('maintenance-account:status'),
  setMaintenanceEnabled: (enabled, password) => ipcRenderer.invoke('maintenance-account:set', enabled, password),
  status: () => ipcRenderer.invoke('admin-sudo:status'),
  needsSetup: () => ipcRenderer.invoke('admin-sudo:setup-required'),
  enroll: (maintenancePassword, password) => ipcRenderer.invoke('admin-sudo:enroll', maintenancePassword, password),
  setEnabled: (enabled, password) => ipcRenderer.invoke('admin-sudo:set', enabled, password),
}
contextBridge.exposeInMainWorld('cncAdminSudo', adminSudo)
const axisProfiles: AxisProfileBridge = {
  read: count => ipcRenderer.invoke('axis-profile:read', count),
  save: (count, revision, changes) => ipcRenderer.invoke('axis-profile:save', count, revision, changes),
  status: () => ipcRenderer.invoke('axis-profile:status'),
  request: count => ipcRenderer.invoke('axis-profile:request', count),
}
contextBridge.exposeInMainWorld('cncAxisProfiles', axisProfiles)

const terminal: TerminalBridge = {
  setEnabled: enabled => ipcRenderer.send('terminal:enabled', enabled),
  open: (id, columns, rows) => ipcRenderer.invoke('terminal:open', id, columns, rows),
  input: (id, text) => ipcRenderer.send('terminal:input', id, text),
  resize: (id, columns, rows) => ipcRenderer.send('terminal:resize', id, columns, rows),
  consumed: (id, length) => ipcRenderer.send('terminal:consumed', id, length),
  close: id => ipcRenderer.send('terminal:close', id),
  onEvent(callback) {
    const receive = (_event: Electron.IpcRendererEvent, message: TerminalEvent) => callback(message)
    ipcRenderer.on('terminal:event', receive)
    return () => ipcRenderer.removeListener('terminal:event', receive)
  },
}
contextBridge.exposeInMainWorld('cncTerminal', terminal)
