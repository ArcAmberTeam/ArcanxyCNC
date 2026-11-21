import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { profileLayouts, type AxisCount, type AxisOperation, type AxisProfile, type AxisProfileStatus } from '../bridge.js'

const execute = promisify(execFile)
const appliance = '/usr/sbin/betterlinuxcnc-appliance'
let submitting = false
let receipt: AxisOperation | null = null

function isCount(value: unknown): value is AxisCount {
  return value === 3 || value === 4 || value === 5
}
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('轴配置服务返回了无效数据')
  return value as Record<string, unknown>
}
async function run(args: string[]) {
  let output: string
  try {
    const result = await execute(appliance, ['axis-profile', ...args], { encoding: 'utf8', timeout: 20000, maxBuffer: 128 * 1024 })
    output = result.stdout
  } catch (error) {
    const failure = error as NodeJS.ErrnoException & { stderr?: string }
    if (failure.code === 'ENOENT') throw new Error('本机尚未安装轴配置服务')
    throw new Error(failure.stderr?.trim().slice(-1024) || '轴配置服务未响应，请刷新状态')
  }
  try { return object(JSON.parse(output)) }
  catch { throw new Error('轴配置服务返回了无效数据') }
}
function operation(value: unknown, scheduled: boolean): AxisOperation {
  const { phase, axis_count, started_at, message } = object(value)
  if (!isCount(axis_count) || typeof started_at !== 'number' || !Number.isFinite(started_at)
    || (phase !== 'scheduled' && phase !== 'switching' && phase !== 'configured' && phase !== 'error')
    || scheduled !== (phase === 'scheduled')) throw new Error('轴配置服务返回了无效的操作状态')
  return { phase, axis_count, started_at, message: typeof message === 'string' ? message : '' }
}

export async function axisProfileStatus(): Promise<AxisProfileStatus> {
  const result = await run(['status'])
  if (result.schema_version !== 1 || result.component !== 'axis-profile' || !Array.isArray(result.profiles)
    || (result.configured_axis_count !== null && !isCount(result.configured_axis_count))) throw new Error('轴配置服务版本或状态无效')
  const selected = result.selected_axis_count === undefined ? result.configured_axis_count : result.selected_axis_count
  if (selected !== null && !isCount(selected)) throw new Error('当前轴方案无效')
  const profiles = result.profiles.map((value): AxisProfile => {
    const { axis_count, axes, available, reason } = object(value)
    if (!isCount(axis_count) || (axes !== profileLayouts[axis_count] && !(axis_count === 5 && axes === 'XYZBC')) || typeof axes !== 'string'
      || typeof available !== 'boolean' || typeof reason !== 'string') throw new Error('轴配置方案无效')
    return { axis_count, axes, available, reason }
  })
  if (profiles.length !== 3 || new Set(profiles.map(item => item.axis_count)).size !== 3) throw new Error('轴配置方案不完整')
  let current = result.operation === null ? null : operation(result.operation, false)
  // systemd may accept a request before the worker replaces the previous operation record.
  if (receipt) {
    if (current && current.started_at >= receipt.started_at && current.axis_count === receipt.axis_count) receipt = null
    else if (current?.phase !== 'switching') {
      current = Date.now() / 1000 - receipt.started_at < 45 ? receipt : { ...receipt, phase: 'unconfirmed' }
    }
  }
  return { profiles, selected_axis_count: selected, configured_axis_count: result.configured_axis_count, operation: current }
}

export async function requestAxisProfile(count: unknown): Promise<AxisOperation> {
  if (!isCount(count)) throw new Error('请选择三轴、四轴或五轴方案')
  if (submitting) throw new Error('轴配置请求正在提交')
  submitting = true
  try {
    const status = await axisProfileStatus()
    if (status.operation?.phase === 'scheduled' || status.operation?.phase === 'switching') throw new Error('正在切换轴配置')
    const profile = status.profiles.find(item => item.axis_count === count)
    if (!profile?.available) throw new Error(profile?.reason || '此方案不可用')
    if (status.selected_axis_count === count) throw new Error('此方案已写入机床配置')
    const accepted = operation(await run(['request', String(count)]), true)
    if (accepted.axis_count !== count) throw new Error('服务返回的轴方案与请求不一致')
    receipt = accepted
    return accepted
  } finally { submitting = false }
}
