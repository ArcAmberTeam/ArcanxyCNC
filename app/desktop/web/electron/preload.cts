import { contextBridge, ipcRenderer } from 'electron'
import type { AdminSudoBridge, AxisProfileBridge, ControlBridge, ControlState, JogRequest, SystemBridge } from '../bridge.js' with { "resolution-mode": "import" }

const bridge: ControlBridge = {
  getState: () => ipcRenderer.invoke('control:state'),
  setFlood: enabled => ipcRenderer.invoke('control:flood', enabled),
  setSpindle: (direction, rpm) => ipcRenderer.invoke('control:spindle', direction, rpm),
  setFeedOverride: ratio => ipcRenderer.invoke('control:feed', ratio),
  startJog: (request: JogRequest) => ipcRenderer.invoke('control:start', request),
  stopJog: () => ipcRenderer.send('control:stop'),
  chooseProgram: () => ipcRenderer.invoke('control:choose-program'),
  startCycle: file => ipcRenderer.invoke('control:cycle', file),
  emergencyStop: () => ipcRenderer.invoke('control:estop'),
  heartbeat: () => ipcRenderer.send('control:heartbeat'),
  onState(callback: (state: ControlState) => void) {
    const listener = (_event: Electron.IpcRendererEvent, state: ControlState) => callback(state)
    ipcRenderer.on('control:state', listener)
    return () => ipcRenderer.removeListener('control:state', listener)
  },
}
contextBridge.exposeInMainWorld('cncControl', bridge)
const systemBridge: SystemBridge = { getInfo: () => ipcRenderer.invoke('system:info') }
contextBridge.exposeInMainWorld('cncSystem', systemBridge)
const adminSudo: AdminSudoBridge = {
  status: () => ipcRenderer.invoke('admin-sudo:status'),
  needsSetup: () => ipcRenderer.invoke('admin-sudo:setup-required'),
  enroll: (code, password) => ipcRenderer.invoke('admin-sudo:enroll', code, password),
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
