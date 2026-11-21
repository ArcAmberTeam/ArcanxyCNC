// Local, PAM-authenticated terminal for the appliance administrator.
import { createRequire } from 'node:module'
import { userInfo } from 'node:os'
import type { IPty } from 'node-pty'
import type { TerminalEvent } from '../bridge.js'
import { maintenanceStatus, requireMaintenance } from './admin-sudo.js'

const require = createRequire(import.meta.url)
const highWater = 128 * 1024
const lowWater = 32 * 1024

function validSize(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0 && value <= 2048
}

//--------//
// BEGIN: MaintenanceTerminal
export class MaintenanceTerminal {
  private enabled = false
  private pending?: string
  private accountTimer?: NodeJS.Timeout
  private session?: { id: string; pty: IPty; outstanding: number; paused: boolean }

  constructor(private readonly emit: (message: TerminalEvent) => void) {}

  setEnabled(enabled: unknown) {
    this.enabled = enabled === true
    if (!this.enabled) this.disconnect()
  }

  disconnect(maintenanceDisabled = false) {
    this.pending = undefined
    if (this.session) {
      const id = this.session.id
      this.close(id)
      this.emit({ id, kind: 'exit', code: 1, maintenanceDisabled })
    }
  }

  private monitorAccount(id: string) {
    this.accountTimer = setTimeout(async () => {
      const state = await maintenanceStatus().catch(() => null)
      if (this.session?.id !== id) return
      if (state === true) this.monitorAccount(id)
      else this.disconnect(state === false)
    }, 5000)
  }

  async open(id: unknown, cols: unknown, rows: unknown) {
    if (!this.enabled || this.pending || this.session) throw new Error('终端未启用或已有会话')
    if (typeof id !== 'string' || !/^[a-f0-9-]{36}$/.test(id) || !validSize(cols) || !validSize(rows)) {
      throw new Error('终端请求无效')
    }
    const uid = process.getuid?.()
    if (process.platform !== 'linux' || !uid || process.geteuid?.() !== uid
        || userInfo().username !== 'linuxcnc') {
      throw new Error('请在机床的 linuxcnc 桌面登录终端')
    }
    this.pending = id
    try {
      await requireMaintenance()
      if (this.pending === id) this.spawn(id, cols, rows)
    } finally {
      if (this.pending === id) this.pending = undefined
    }
  }

  private spawn(id: string, cols: number, rows: number) {
    // su prompts on its own terminal and checks the administrator's actual PAM credentials.
    // Its login shell cannot inherit renderer-controlled commands, paths or environment.
    const native = require('node-pty') as typeof import('node-pty')
    const pty = native.spawn('/usr/bin/su', ['--pty', '--login', '--shell', '/bin/bash', 'cnc_admin'], {
      cols, rows, cwd: '/', name: 'xterm-256color',
      env: { PATH: '/usr/bin:/bin', TERM: 'xterm-256color', LANG: 'C.UTF-8' },
    })
    const session = { id, pty, outstanding: 0, paused: false }
    this.session = session
    this.monitorAccount(id)
    pty.onData(text => {
      if (this.session !== session) return
      session.outstanding += text.length
      if (!session.paused && session.outstanding >= highWater) {
        pty.pause()
        session.paused = true
      }
      this.emit({ id, kind: 'data', text })
    })
    pty.onExit(({ exitCode }) => {
      if (this.session !== session) return
      clearTimeout(this.accountTimer)
      this.session = undefined
      this.emit({ id, kind: 'exit', code: exitCode })
    })
  }

  input(id: unknown, text: unknown) {
    const session = this.session
    if (session && session.id === id && typeof text === 'string' && text.length <= 65536) session.pty.write(text)
  }

  resize(id: unknown, cols: unknown, rows: unknown) {
    const session = this.session
    if (!session || session.id !== id || !validSize(cols) || !validSize(rows)) return
    try {
      session.pty.resize(cols, rows)
    } catch {
      // The PTY can close before node-pty delivers its exit notification.
      this.close(id)
      this.emit({ id: session.id, kind: 'exit', code: 1 })
    }
  }

  consumed(id: unknown, length: unknown) {
    const session = this.session
    if (!session || session.id !== id || typeof length !== 'number' || !Number.isInteger(length)
        || length <= 0 || length > session.outstanding) return
    session.outstanding -= length
    if (session.paused && session.outstanding <= lowWater) {
      session.paused = false
      session.pty.resume()
    }
  }

  close(id: unknown) {
    if (this.pending === id) this.pending = undefined
    const session = this.session
    if (!session || session.id !== id) return
    clearTimeout(this.accountTimer)
    this.session = undefined
    if (session.paused) session.pty.resume()
    session.pty.kill('SIGTERM')
  }
}
// END: MaintenanceTerminal
//--------//
