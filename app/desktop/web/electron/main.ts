import { app, BrowserWindow, dialog, ipcMain, type IpcMainEvent, type IpcMainInvokeEvent } from 'electron'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { performance } from 'node:perf_hooks'
import { ControllerSession } from './session.js'
import { ManualController } from './manual-controller.js'
import { MaintenanceTerminal } from './maintenance-terminal.js'
import { getSystemInfo } from './system-info.js'
import { adminSetupRequired, adminSudoStatus, enrollAdmin, maintenanceStatus, setAdminSudo, setMaintenanceEnabled } from './admin-sudo.js'
import { axisParameters } from './axis-parameters.js'
import { axisProfileStatus, requestAxisProfile } from './maintenance.js'
import type { ControlState } from '../bridge.js'

const kiosk = process.argv.includes('--kiosk') || process.env.BETTERCNC_KIOSK === '1'
if (process.platform === 'linux' && (kiosk || process.argv.includes('--kiosk-status'))) {
  app.disableHardwareAcceleration()
}
const directory = dirname(fileURLToPath(import.meta.url))
const page = join(directory, '../../dist/index.html')
const argument = (name: string) => {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}
const session = new ControllerSession(argument('--socket') || process.env.BETTERCNC_SOCKET, argument('--ini') || argument('-ini'))
let window: BrowserWindow | undefined
let timer: NodeJS.Timeout | undefined
const terminal = new MaintenanceTerminal(message => {
  if (window && !window.webContents.isDestroyed()) window.webContents.send('terminal:event', message)
})
let listening = false
let sequence = 0
let inFlight: number | undefined
let latest: ControlState | undefined

function publishState(state: ControlState) {
  if (!listening || !window || window.webContents.isDestroyed()) return
  if (inFlight !== undefined) {
    latest = state
    return
  }
  inFlight = ++sequence
  window.webContents.send('control:state', inFlight, state)
}

const controller = new ManualController(session, () => performance.now(),
  () => !!window && window.isFocused() && !window.isMinimized() && window.isVisible(),
  publishState)

function trustedSender(event: IpcMainEvent | IpcMainInvokeEvent) {
  return !!window && event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame
    && event.senderFrame?.url === pathToFileURL(page).href
}

function authorize(event: IpcMainEvent | IpcMainInvokeEvent) {
  if (!trustedSender(event)) throw new Error('无效控制页面来源')
}

app.whenReady().then(async () => {
  if (process.argv.includes('--kiosk-status')) {
    window = new BrowserWindow({
      title: 'BetterLinuxCNC', fullscreen: true, frame: false, focusable: false, show: false,
      skipTaskbar: true, backgroundColor: '#f5f5f7',
      webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false },
    })
    window.removeMenu()
    window.once('ready-to-show', () => {
      window?.showInactive()
      if (window?.isVisible()) process.stdout.write('{"kioskStatus":"visible"}\n')
    })
    await window.loadFile(join(dirname(page), 'kiosk-status.html'))
    return
  }
  ipcMain.handle('terminal:open', (event, id, cols, rows) => { authorize(event); return terminal.open(id, cols, rows) })
  ipcMain.on('terminal:enabled', (event, enabled) => { if (trustedSender(event)) terminal.setEnabled(enabled) })
  ipcMain.on('terminal:input', (event, id, text) => { if (trustedSender(event)) terminal.input(id, text) })
  ipcMain.on('terminal:resize', (event, id, cols, rows) => { if (trustedSender(event)) terminal.resize(id, cols, rows) })
  ipcMain.on('terminal:consumed', (event, id, length) => { if (trustedSender(event)) terminal.consumed(id, length) })
  ipcMain.on('terminal:close', (event, id) => { if (trustedSender(event)) terminal.close(id) })
  ipcMain.handle('system:info', event => { authorize(event); return getSystemInfo() })
  ipcMain.handle('maintenance-account:status', event => { authorize(event); return maintenanceStatus() })
  ipcMain.handle('maintenance-account:set', async (event, enabled: unknown, password: unknown) => {
    authorize(event)
    if (!window?.isFocused()) throw new Error('请在机床屏幕上操作')
    const state = await setMaintenanceEnabled(enabled, password)
    if (!state) terminal.disconnect(true)
    return state
  })
  ipcMain.handle('admin-sudo:status', event => { authorize(event); return adminSudoStatus() })
  ipcMain.handle('admin-sudo:setup-required', event => { authorize(event); return adminSetupRequired() })
  ipcMain.handle('admin-sudo:enroll', (event, maintenancePassword: unknown, password: unknown) => {
    authorize(event)
    return enrollAdmin(maintenancePassword, password)
  })
  ipcMain.handle('admin-sudo:set', (event, enabled: unknown, password: unknown) => {
    authorize(event)
    return setAdminSudo(enabled, password)
  })
  ipcMain.handle('axis-profile:read', (event, count: unknown) => { authorize(event); return axisParameters(count) })
  ipcMain.handle('axis-profile:save', (event, count: unknown, revision: unknown, changes: unknown) => {
    authorize(event)
    return axisParameters(count, { revision, changes })
  })
  ipcMain.handle('axis-profile:status', event => { authorize(event); return axisProfileStatus() })
  ipcMain.handle('axis-profile:request', (event, count: unknown) => { authorize(event); return requestAxisProfile(count) })
  ipcMain.handle('control:state', event => {
    authorize(event)
    return controller.state
  })
  ipcMain.on('control:state-consumed', (event, id: unknown) => {
    if (!trustedSender(event) || inFlight === undefined || id !== inFlight) return
    inFlight = undefined
    if (latest) {
      const state = latest
      latest = undefined
      publishState(state)
    }
  })
  ipcMain.handle('control:home-all', (event, confirmed: unknown) => { authorize(event); return controller.homeAll(confirmed) })
  ipcMain.handle('control:flood', (event, enabled: unknown) => { authorize(event); return controller.setFlood(enabled) })
  ipcMain.handle('control:spindle', (event, direction: unknown, rpm?: unknown) => { authorize(event); return controller.setSpindle(direction, rpm) })
  ipcMain.handle('control:feed', (event, ratio: unknown) => { authorize(event); return controller.setFeedOverride(ratio) })
  ipcMain.handle('control:start', (event, request: unknown) => { authorize(event); return controller.start(request) })
  ipcMain.handle('control:choose-program', async event => {
    authorize(event)
    const owner = window
    if (!owner || !controller.state.connected) throw new Error('控制服务未就绪')
    const result = await dialog.showOpenDialog(owner, {
      title: '选择加工程序', properties: ['openFile'], defaultPath: controller.programDirectory,
      filters: [{ name: '加工程序', extensions: ['ngc', 'nc', 'gcode'] }],
    })
    if (!result.canceled && result.filePaths.length === 1) {
      authorize(event)
      await controller.loadProgram(result.filePaths[0])
    }
  })
  ipcMain.handle('control:cycle', (event, file: unknown) => { authorize(event); return controller.startCycle(file) })
  ipcMain.handle('control:estop', event => { authorize(event); return controller.emergencyStop() })
  ipcMain.handle('control:estop-reset', (event, confirmed: unknown) => { authorize(event); return controller.resetEmergencyStop(confirmed) })
  ipcMain.on('control:heartbeat', event => { try { authorize(event); controller.heartbeat() } catch {} })
  ipcMain.on('control:stop', event => { try { authorize(event); void controller.stop() } catch {} })
  window = new BrowserWindow({
    width: 1024, height: 632, minWidth: 760, minHeight: 600, backgroundColor: '#f5f5f7',
    title: 'BetterLinuxCNC', autoHideMenuBar: true,
    fullscreen: process.argv.includes('--fullscreen') || process.env.BETTERCNC_FULLSCREEN === '1',
    kiosk,
    webPreferences: { preload: join(directory, 'preload.cjs'), contextIsolation: true, sandbox: true, nodeIntegration: false, spellcheck: false },
  })
  window.removeMenu()
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  window.webContents.on('will-navigate', event => { void controller.stop(); event.preventDefault() })
  window.webContents.on('did-start-loading', () => {
    listening = false
    inFlight = undefined
    latest = undefined
    terminal.setEnabled(false)
    void controller.stop()
  })
  window.webContents.on('dom-ready', () => { listening = true })
  window.webContents.on('render-process-gone', () => { terminal.setEnabled(false); controller.close() })
  window.webContents.on('unresponsive', () => { void controller.stop() })
  window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false))
  window.on('blur', () => { void controller.stop() })
  window.on('minimize', () => { void controller.stop() })
  window.on('hide', () => { void controller.stop() })
  window.on('closed', () => { terminal.setEnabled(false); controller.close(); window = undefined })
  await window.loadFile(page)
  timer = setInterval(() => { controller.watchdog(); void controller.poll() }, 100)
  void controller.poll()
  if (process.argv.includes('--smoke-test')) setTimeout(() => app.quit(), 1500)
}).catch(error => { console.error(error); app.exit(1) })

app.on('before-quit', () => { terminal.setEnabled(false); if (timer) clearInterval(timer); controller.close() })
app.on('window-all-closed', () => app.quit())
process.on('SIGTERM', () => app.quit())
process.on('SIGINT', () => app.quit())
