export const jogAxes = ['X', 'Y', 'Z', 'A', 'B', 'C'] as const
export type JogAxis = typeof jogAxes[number]
export type JogDirection = -1 | 1

export const profileLayouts = { 3: 'XYZ', 4: 'XYZC', 5: 'XYZAC' } as const
export type AxisCount = keyof typeof profileLayouts
export interface AxisProfile {
  axis_count: AxisCount
  axes: string
  available: boolean
  reason: string
}
export interface AxisOperation {
  axis_count: AxisCount
  started_at: number
  phase: 'scheduled' | 'switching' | 'configured' | 'error' | 'unconfirmed'
  message: string
}
export interface AxisProfileStatus {
  profiles: AxisProfile[]
  selected_axis_count?: AxisCount | null
  configured_axis_count: AxisCount | null
  operation: AxisOperation | null
}
export interface AxisParameterDocument { revision: string; values: Record<string, string> }
export interface AxisProfileBridge {
  read(count: AxisCount): Promise<AxisParameterDocument>
  save(count: AxisCount, revision: string, changes: Record<string, string>): Promise<AxisParameterDocument>
  status(): Promise<AxisProfileStatus>
  request(count: AxisCount): Promise<AxisOperation>
}
export type AxisParameterFiles = Pick<AxisProfileBridge, 'read'> & Partial<Pick<AxisProfileBridge, 'save'>>

export interface ActiveAxis {
  name: string
  unit: 'mm' | 'deg'
  min: number | null
  max: number | null
  maxFeed: number | null
}

export interface SystemInfo {
  schemaVersion: 1
  cpu: { model: string | null; logicalCores: number } | null
  gpus: Array<{ model: string; vendorId: string; deviceId: string; driver: string | null }> | null
  memory: { totalBytes: number; availableBytes: number | null } | null
  kernel: string | null
}

export interface SystemBridge {
  getInfo(): Promise<SystemInfo>
}

export const maintenanceRequiredMessage = '请先在开发者选项中启用 cnc-maint 运维账户并设置密码'

export interface AdminSudoBridge {
  maintenanceStatus(): Promise<boolean>
  setMaintenanceEnabled(enabled: boolean, password: string): Promise<boolean>
  status(): Promise<boolean>
  needsSetup(): Promise<boolean>
  enroll(maintenancePassword: string, newPassword: string): Promise<boolean>
  setEnabled(enabled: boolean, password: string): Promise<boolean>
}

export type TerminalEvent =
  | { id: string; kind: 'data'; text: string }
  | { id: string; kind: 'exit'; code: number; maintenanceDisabled?: boolean }

export interface TerminalBridge {
  setEnabled(enabled: boolean): void
  open(id: string, columns: number, rows: number): Promise<void>
  input(id: string, text: string): void
  resize(id: string, columns: number, rows: number): void
  consumed(id: string, length: number): void
  close(id: string): void
  onEvent(listener: (event: TerminalEvent) => void): () => void
}

declare global {
  interface Window { cncTerminal?: TerminalBridge; cncSystem?: SystemBridge; cncAxisProfiles?: AxisProfileBridge; cncAdminSudo?: AdminSudoBridge }
}

export interface MachineReadings {
  flood: boolean | null
  rtcpModel: string | null
  rtcpGeometry: Record<string, number>
  spindleRpm: number | null
  spindleTarget: number | null
  spindleMin: number | null
  spindleMax: number | null
  canForward: boolean
  canReverse: boolean
  canStopSpindle: boolean
  spindleDirection: number | null
  feedRatio: number | null
  feedMax: number | null
  workSystem: string | null
  position: Partial<Record<JogAxis, number>>
  canSetFlood: boolean
  canSetFeed: boolean
}

export interface JogRequest {
  axis: JogAxis
  direction: JogDirection
  feedRate: number
}

export interface ControlState {
  readings: MachineReadings | null
  serviceConnected: boolean
  connected: boolean
  canJog: boolean
  canHomeAll: boolean
  programFile: string | null
  canStartCycle: boolean
  canEstop: boolean
  estop: boolean | null
  jogging: boolean
  activeAxes: readonly ActiveAxis[] | null
  axes: Partial<Record<JogAxis, { maxFeed: number; unit: 'mm' | 'deg' }>>
  reason: string
  error: string
  commandState: string
}

export interface ControlBridge {
  homeAll(clearanceConfirmed: true): Promise<void>
  setSpindle(direction: -1 | 0 | 1, rpm?: number): Promise<void>
  setFlood(enabled: boolean): Promise<void>
  setFeedOverride(ratio: number): Promise<void>
  getState(): Promise<ControlState>
  onState(callback: (state: ControlState) => void): () => void
  startJog(request: JogRequest): Promise<void>
  stopJog(): void
  chooseProgram(): Promise<void>
  startCycle(file: string): Promise<void>
  emergencyStop(): Promise<void>
  resetEmergencyStop(confirmed: true): Promise<void>
  heartbeat(): void
}

export function offlineState(reason: string): ControlState {
  return {
    serviceConnected: false, connected: false, canJog: false, canHomeAll: false, canEstop: false, estop: null,
    programFile: null, canStartCycle: false, jogging: false, axes: {}, activeAxes: null, readings: null, reason, error: '', commandState: 'disconnected',
  }
}
