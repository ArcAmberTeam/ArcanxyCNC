import { app, BrowserWindow, dialog, ipcMain, type IpcMainEvent, type IpcMainInvokeEvent } from 'electron'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { performance } from 'node:perf_hooks'
import { ControllerSession } from './session.js'
import { ManualController } from './manual-controller.js'
import { getSystemInfo } from './system-info.js'
import { adminSetupRequired, adminSudoStatus, enrollAdmin, setAdminSudo } from './admin-sudo.js'
import { axisParameters } from './axis-parameters.js'
import { axisProfileStatus, requestAxisProfile } from './maintenance.js'

const directory = dirname(fileURLToPath(import.meta.url))
const page = join(directory, '../../dist/index.html')
const argument = (name: string) => {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}
const session = new ControllerSession(argument('--socket') || process.env.BETTERCNC_SOCKET, argument('--ini') || argument('-ini'))
let window: BrowserWindow | undefined
let timer: NodeJS.Timeout | undefined
const controller = new ManualController(session, () => performance.now(),
  () => !!window && window.isFocused() && !window.isMinimized() && window.isVisible(),
  state => { if (window && !window.webContents.isDestroyed()) window.webContents.send('control:state', state) })

function authorize(event: IpcMainEvent | IpcMainInvokeEvent) {
  if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame
    || event.senderFrame?.url !== pathToFileURL(page).href) throw new Error('无效控制页面来源')
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
  ipcMain.handle('system:info', event => { authorize(event); return getSystemInfo() })
  ipcMain.handle('admin-sudo:status', event => { authorize(event); return adminSudoStatus() })
  ipcMain.handle('admin-sudo:setup-required', event => { authorize(event); return adminSetupRequired() })
  ipcMain.handle('admin-sudo:enroll', (event, code: unknown, password: unknown) => {
    authorize(event)
    return enrollAdmin(code, password)
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
  ipcMain.handle('control:state', event => { authorize(event); return controller.state })
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
  ipcMain.on('control:heartbeat', event => { try { authorize(event); controller.heartbeat() } catch {} })
  ipcMain.on('control:stop', event => { try { authorize(event); void controller.stop() } catch {} })
  window = new BrowserWindow({
    width: 1024, height: 632, minWidth: 760, minHeight: 600, backgroundColor: '#f5f5f7',
    title: 'BetterLinuxCNC', autoHideMenuBar: true,
    fullscreen: process.argv.includes('--fullscreen') || process.env.BETTERCNC_FULLSCREEN === '1',
    kiosk: process.argv.includes('--kiosk') || process.env.BETTERCNC_KIOSK === '1',
    webPreferences: { preload: join(directory, 'preload.cjs'), contextIsolation: true, sandbox: true, nodeIntegration: false, spellcheck: false },
  })
  window.removeMenu()
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  window.webContents.on('will-navigate', event => { void controller.stop(); event.preventDefault() })
  window.webContents.on('did-start-loading', () => { void controller.stop() })
  window.webContents.on('render-process-gone', () => controller.close())
  window.webContents.on('unresponsive', () => { void controller.stop() })
  window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false))
  window.on('blur', () => { void controller.stop() })
  window.on('minimize', () => { void controller.stop() })
  window.on('hide', () => { void controller.stop() })
  window.on('closed', () => { controller.close(); window = undefined })
  await window.loadFile(page)
  timer = setInterval(() => { controller.watchdog(); void controller.poll() }, 100)
  void controller.poll()
  if (process.argv.includes('--smoke-test')) setTimeout(() => app.quit(), 1500)
}).catch(error => { console.error(error); app.exit(1) })

app.on('before-quit', () => { if (timer) clearInterval(timer); controller.close() })
app.on('window-all-closed', () => app.quit())
process.on('SIGTERM', () => app.quit())
process.on('SIGINT', () => app.quit())
