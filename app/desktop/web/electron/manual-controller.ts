import { jogAxes, offlineState, type ControlState, type JogAxis, type JogRequest } from '../bridge.js'
import { RemoteError } from './session.js'
import { activeAxisSettings, machineReadings } from './machine-readings.js'

export interface ControlTransport {
  readonly connected: boolean
  connect(): Promise<void>
  close(): void
  request(method: string, params: Record<string, unknown>, current?: () => boolean): Promise<Record<string, unknown>>
}

const positive = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value > 0
const record = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('控制服务返回了无效状态')
  return value as Record<string, unknown>
}

// Only explicit, one-to-one trivkins mappings can label a joint with an axis name.
function mappedJoint(snapshot: Record<string, unknown>, axis: JogAxis): number | undefined {
  const map = snapshot.jointMap
  if (snapshot.kinematicsModel !== 'trivkins' || !Number.isInteger(snapshot.jointCount)
    || Number(snapshot.jointCount) < 1 || Number(snapshot.jointCount) > 9
    || !map || typeof map !== 'object' || Array.isArray(map)) return
  const entries = map as Record<string, unknown>
  const selected = entries[axis]
  if (!Array.isArray(selected) || selected.length !== 1 || !Number.isInteger(selected[0])
    || selected[0] < 0 || selected[0] >= Number(snapshot.jointCount)) return
  const joint = selected[0] as number
  if (Object.values(entries).some(value => !Array.isArray(value))
    || Object.values(entries).flat().filter(value => value === joint).length !== 1) return
  return joint
}

//--------//
// BEGIN: ManualController
// Owns desktop jogging leases; the service remains the authority for machine interlocks.
export class ManualController {
  state = offlineState('正在连接本地控制服务')
  private snapshot: Record<string, unknown> = {}
  private sampledAt = -Infinity
  private heartbeatAt = -Infinity
  private generation = 0
  private held = false
  private starting = false
  private submittingHome = false
  private resetting = false
  private checkResetFeedback?: () => void
  private stopping?: Promise<void>
  private polling = false
  private localCommandError = ''
  private nextConnect = 0
  private closed = false
  private jogTarget?: { axis: JogAxis; mode: 'joint' | 'world'; joint?: number; units: number }

  constructor(
    private transport: ControlTransport,
    private now: () => number,
    private focused: () => boolean,
    private publish: (state: ControlState) => void,
  ) {}

  heartbeat() { if (!this.closed) this.heartbeatAt = this.now() }
  private fresh() { return !this.closed && this.focused() && this.now() - this.heartbeatAt < 350 }
  private emit() {
    this.checkResetFeedback?.()
    this.publish({ ...this.state })
  }

  private update(value: unknown) {
    const data = record(value)
    if (typeof data.connected !== 'boolean' || !Array.isArray(data.axes)
      || !data.axes.every(axis => typeof axis === 'string' && /^[XYZABCUVW]$/.test(axis))) {
      throw new Error('控制服务返回了无效轴配置')
    }
    this.snapshot = data
    this.sampledAt = this.now()
    const capabilities = record(data.capabilities)
    const axes: ControlState['axes'] = {}
    const activeAxes = data.connected ? activeAxisSettings(data.axes, data) : null
    for (const axis of activeAxes ?? []) {
      const name = jogAxes.find(name => name === axis.name)
      if (name && axis.maxFeed !== null && (data.motionMode !== 'joint' || mappedJoint(data, name) !== undefined)) {
        axes[name] = { maxFeed: axis.maxFeed, unit: axis.unit }
      }
    }
    let reason = ''
    if (!data.connected) reason = '控制服务已连接，LinuxCNC 尚未就绪'
    else if (data.estop !== false) reason = '机床处于急停状态'
    else if (data.powered !== true) reason = '机床尚未启动'
    else if (data.motionMode !== 'world' && data.motionMode !== 'joint') reason = '机床运动模式未知'
    else if (!positive(data.linearUnits) || !positive(data.angularUnits)) reason = '机床单位信息不可用'
    else if (capabilities['jog.start'] !== true && !this.held) reason = '当前机床状态不允许点动'
    else if (!Object.keys(axes).length) reason = data.motionMode === 'joint'
      ? '机床未提供唯一的轴与关节映射及速度限制' : '机床未提供可用轴和速度限制'
    const commandError = data.commandState === 'error' || data.commandState === 'unknown'
      ? String(data.commandMessage || '控制命令结果异常，请检查机床状态') : ''
    this.state = {
      serviceConnected: true, connected: data.connected,
      readings: machineReadings(data, capabilities),
      canJog: !reason && capabilities['jog.start'] === true && !this.held && !this.starting && !this.stopping,
      jogMode: data.connected && (data.motionMode === 'joint' || data.motionMode === 'world') ? data.motionMode : null,
      canSetPower: data.connected && capabilities['machine.power'] === true && !this.held && !this.starting && !this.stopping,
      powered: data.connected && typeof data.powered === 'boolean' ? data.powered : null,
      canHomeAll: data.connected && capabilities['machine.power-and-home'] === true && !this.held,
      programFile: data.connected && typeof data.file === 'string' ? data.file : null,
      canStartCycle: data.connected && capabilities['program.home-and-run'] === true,
      canEstop: data.connected && capabilities['machine.estop'] === true,
      estop: data.connected && typeof data.estop === 'boolean' ? data.estop : null,
      jogging: this.held, activeAxes, axes, reason,
      error: commandError || this.localCommandError,
      commandState: typeof data.commandState === 'string' ? data.commandState : 'unknown',
    }
    this.emit()
    if (this.held && (reason || commandError || !this.sameJogTarget())) void this.stop()
  }

  private sameJogTarget() {
    const target = this.jogTarget
    return !!target && this.snapshot.motionMode === target.mode
      && (target.mode !== 'joint' || mappedJoint(this.snapshot, target.axis) === target.joint)
      && ('ABC'.includes(target.axis) ? this.snapshot.angularUnits : this.snapshot.linearUnits) === target.units
  }

  private disconnect(error: unknown) {
    this.generation++
    this.held = false
    this.jogTarget = undefined
    this.sampledAt = -Infinity
    this.transport.close()
    this.nextConnect = this.now() + 1000
    this.state = offlineState('本地控制服务未连接')
    if (error instanceof RemoteError && error.code === 'result_unknown') {
      this.localCommandError = error.message
      this.state.commandState = 'unknown'
    }
    const waiting = error instanceof Error && (error as NodeJS.ErrnoException).code === 'ENOENT'
    this.state.error = this.localCommandError || (waiting ? '正在等待本机控制服务启动' : error instanceof Error ? error.message : String(error))
    this.emit()
  }

  async poll() {
    if (this.closed || this.polling || (!this.transport.connected && this.now() < this.nextConnect)) return
    this.polling = true
    const generation = this.generation
    try {
      if (!this.transport.connected) await this.transport.connect()
      if (this.closed) { this.transport.close(); return }
      const renew = this.held && this.fresh()
      const result = await this.transport.request('session.status', { jog_lease: renew },
        () => !this.closed && (!renew || (generation === this.generation && this.held && this.fresh())))
      if (!this.closed) this.update(result)
    } catch (error) {
      if (!this.closed && (generation === this.generation || !this.transport.connected)) this.disconnect(error)
    } finally { this.polling = false }
  }

  // Runs independently of awaited socket requests and revokes unsent starts.
  watchdog() {
    if (this.closed) return
    if ((this.held || this.starting) && (!this.fresh() || this.now() - this.sampledAt >= 500)) {
      void this.stop()
    }
    if (this.now() - this.sampledAt >= 500 && (this.state.canEstop || this.state.estop !== null || this.state.canJog || this.state.canHomeAll || this.state.readings || this.state.programFile !== null)) {
      this.state = { ...this.state, readings: null, activeAxes: null, axes: {}, programFile: null, canStartCycle: false, canJog: false, jogMode: null, canSetPower: false, powered: null, canHomeAll: false, canEstop: false, estop: null, reason: '机床状态已过期，等待更新' }
      this.emit()
    }
  }

  async start(value: unknown) {
    const request = record(value)
    if (Object.keys(request).sort().join(',') !== 'axis,direction,feedRate'
      || !jogAxes.includes(request.axis as JogAxis) || ![-1, 1].includes(request.direction as number)
      || !positive(request.feedRate)) throw new Error('点动参数无效')
    const { axis, direction, feedRate } = request as unknown as JogRequest
    const configured = this.state.axes[axis]
    if (!this.transport.connected || !this.state.canJog || this.starting || this.stopping || this.held
      || !configured || feedRate > configured.maxFeed || !this.fresh() || this.now() - this.sampledAt >= 500) {
      throw new Error(this.state.reason || '当前轴、速度或界面状态不允许点动')
    }
    const units = 'ABC'.includes(axis) ? this.snapshot.angularUnits : this.snapshot.linearUnits
    if (!positive(units)) throw new Error('机床单位信息不可用')
    const mode = this.snapshot.motionMode
    if (mode !== 'joint' && mode !== 'world') throw new Error('机床运动模式未知')
    const joint = mode === 'joint' ? mappedJoint(this.snapshot, axis) : undefined
    if (mode === 'joint' && joint === undefined) throw new Error('当前轴没有唯一的关节映射')
    const generation = ++this.generation
    this.jogTarget = { axis, mode, joint, units }
    this.held = true
    this.starting = true
    this.localCommandError = ''
    this.state = { ...this.state, canJog: false, canSetPower: false, canHomeAll: false, jogging: true, error: '' }
    this.emit()
    try {
      const result = await this.transport.request('command.execute', {
        action: 'jog.start', payload: {
          axis, direction, mode, ...(mode === 'joint' ? { joint } : {}),
          velocity: feedRate * units / 60, increment: mode === 'joint' ? 0.1 * units : 0,
        },
      }, () => generation === this.generation && this.held && this.sameJogTarget() && this.fresh()
        && this.now() - this.sampledAt < 500 && feedRate <= (this.state.axes[axis]?.maxFeed ?? 0))
      this.accept(result)
      if (generation !== this.generation || !this.fresh()) await this.stop()
    } catch (error) {
      await this.stop()
      if (!this.transport.connected || error instanceof RemoteError && error.code === 'result_unknown') this.disconnect(error)
      else if (generation === this.generation - 1) this.report(error)
      throw error
    } finally { this.starting = false }
  }

  private accept(response: Record<string, unknown>) {
    if (typeof response.accepted !== 'boolean') throw new RemoteError('result_unknown', '命令结果未知，不会自动重发')
    try { this.update(response.snapshot) }
    catch { throw new RemoteError('result_unknown', '命令反馈无效，不会自动重发') }
    if (!response.accepted) throw new Error(String(this.snapshot.commandMessage || '控制服务拒绝了操作'))
  }

  private report(error: unknown) {
    this.localCommandError = error instanceof Error ? error.message : String(error)
    this.state = { ...this.state, error: this.localCommandError }
    this.emit()
  }

  stop(): Promise<void> {
    this.generation++
    const needsStop = this.held || this.starting
    this.held = false
    this.jogTarget = undefined
    this.state = { ...this.state, jogging: false, canJog: false }
    this.emit()
    if (this.stopping) return this.stopping
    if (!needsStop || !this.transport.connected) return Promise.resolve()
    this.stopping = this.transport.request('command.execute', { action: 'jog.stop', payload: {} })
      .then(result => this.accept(result))
      .catch(error => this.disconnect(error))
      .finally(() => { this.stopping = undefined })
    return this.stopping
  }

  async emergencyStop() {
    if (!this.transport.connected || !this.state.canEstop) throw new Error('控制服务未就绪，无法发送急停')
    // Revocation is immediate; stopping and emergency-stop requests preserve socket ordering.
    void this.stop()
    try {
      this.accept(await this.transport.request('command.execute', { action: 'machine.estop', payload: { enabled: true } }))
    } catch (error) { this.disconnect(error); throw error }
  }

  async resetEmergencyStop(confirmed: unknown) {
    if (confirmed !== true) throw new Error('请先确认机床无异常')
    if (this.resetting) throw new Error('正在等待急停复位反馈')
    this.resetting = true
    try {
      await this.sendControl('machine.estop', { enabled: false },
        () => this.state.canEstop && this.state.estop === true)
      const deadline = this.now() + 12000
      await new Promise<void>((resolve, reject) => {
        this.checkResetFeedback = () => {
          if (this.closed || this.state.estop === null) reject(new Error('机床状态不可用，无法确认急停是否解除'))
          else if (!this.state.estop) resolve()
          else if (this.state.commandState === 'error' || this.state.commandState === 'unknown' || this.now() >= deadline) {
            reject(new Error('机床仍处于急停，请检查外部急停输入和当前机床配置。'))
          }
        }
        this.checkResetFeedback()
      })
    } finally {
      this.checkResetFeedback = undefined
      this.resetting = false
    }
  }

  get programDirectory() {
    return typeof this.snapshot.programPrefix === 'string' ? this.snapshot.programPrefix : undefined
  }

  async loadProgram(path: string) {
    // File selection returns from a native modal; the renderer heartbeat may have paused.
    const generation = this.generation
    const current = () => !this.closed && this.transport.connected && generation === this.generation
      && this.state.connected && !this.held && record(this.snapshot.capabilities)['file.open'] === true
    this.accept(await this.transport.request('command.execute', { action: 'file.open', payload: { path } }, current))
  }

  async startCycle(file: unknown) {
    if (typeof file !== 'string' || !file) throw new Error('请先选择加工程序')
    await this.sendControl('program.home-and-run', { file },
      () => this.state.canStartCycle && this.state.programFile === file)
  }

  async homeAll(confirmed: unknown) {
    if (confirmed !== true) throw new Error('请先确认回零路径无遮挡')
    if (this.submittingHome) throw new Error('回零请求正在提交')
    this.submittingHome = true
    try {
      await this.sendControl('machine.power-and-home', { clearanceConfirmed: true },
        () => this.state.canHomeAll && !this.starting && !this.stopping)
    } finally { this.submittingHome = false }
  }

  async setSpindle(direction: unknown, rpm?: unknown) {
    if (direction === 0 && rpm === undefined) {
      await this.sendControl('spindle.stop', {}, () => this.state.readings?.canStopSpindle === true)
      return
    }
    if ((direction !== 1 && direction !== -1) || !positive(rpm)) throw new Error('主轴方向或转速无效')
    await this.sendControl(direction === 1 ? 'spindle.forward' : 'spindle.reverse', { speed: rpm }, () => {
      const readings = this.state.readings
      return !!readings && (direction === 1 ? readings.canForward : readings.canReverse)
        && (readings.spindleMin === null || rpm >= readings.spindleMin)
        && (readings.spindleMax === null || rpm <= readings.spindleMax)
    })
  }

  async setFlood(enabled: unknown) {
    if (typeof enabled !== 'boolean') throw new Error('冷却开关参数无效')
    await this.sendControl('coolant.flood', { enabled }, () => this.state.readings?.canSetFlood === true)
  }

  async setPower(enabled: unknown) {
    if (typeof enabled !== 'boolean') throw new Error('使能参数无效')
    await this.sendControl('machine.power', { enabled }, () => this.state.canSetPower
      && this.state.powered !== null && this.state.powered !== enabled
      && (!enabled || this.state.estop === false))
  }

  async setFeedOverride(value: unknown) {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) throw new Error('进给倍率无效')
    await this.sendControl('override.feed', { value }, () => {
      const readings = this.state.readings
      return !!readings?.canSetFeed && readings.feedMax !== null && value <= readings.feedMax
    })
  }

  private async sendControl(action: 'machine.estop' | 'machine.power' | 'machine.power-and-home' | 'program.home-and-run' | 'coolant.flood' | 'override.feed' | 'spindle.forward' | 'spindle.reverse' | 'spindle.stop', payload: Record<string, unknown>, allowed: () => boolean) {
    const generation = this.generation
    const current = () => this.transport.connected && this.fresh() && this.now() - this.sampledAt < 500
      && (action === 'spindle.stop' || (generation === this.generation && !this.held)) && allowed()
    if (!current()) throw new Error('当前机床状态不允许此操作')
    try {
      this.accept(await this.transport.request('command.execute', { action, payload }, current))
    } catch (error) {
      if (!this.transport.connected || error instanceof RemoteError && error.code === 'result_unknown') this.disconnect(error)
      throw error
    }
  }

  close() {
    this.closed = true
    this.checkResetFeedback?.()
    this.generation++
    this.held = false
    this.jogTarget = undefined
    this.heartbeatAt = -Infinity
    this.transport.close()
  }
}
// END: ManualController
//--------//
