import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { performance } from 'node:perf_hooks'
import type { SystemInfo } from '../bridge.js'

const execute = promisify(execFile)
const executable = '/usr/lib/betterlinuxcnc/system-info/betterlinuxcnc-system-info'
const text = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 1024
const nullableText = (value: unknown) => value === null || text(value)
const positiveInteger = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)

export function parseSystemInfo(raw: string): SystemInfo {
  const value: unknown = JSON.parse(raw)
  const invalid = () => { throw new Error('系统信息服务返回的数据格式无效') }
  if (!record(value) || value.schemaVersion !== 1) return invalid()
  if (value.cpu !== null && (!record(value.cpu) || !nullableText(value.cpu.model) || !positiveInteger(value.cpu.logicalCores))) return invalid()
  if (!nullableText(value.kernel)) return invalid()
  if (value.memory !== null) {
    if (!record(value.memory) || !positiveInteger(value.memory.totalBytes)) return invalid()
    const available = value.memory.availableBytes
    if (available !== null && (typeof available !== 'number' || !Number.isSafeInteger(available) || available < 0 || available > value.memory.totalBytes)) return invalid()
  }
  if (value.gpus !== null && (!Array.isArray(value.gpus) || value.gpus.length > 32 || !value.gpus.every(gpu =>
    record(gpu) && text(gpu.model) && nullableText(gpu.driver)
    && typeof gpu.vendorId === 'string' && /^[0-9a-f]{4}$/.test(gpu.vendorId)
    && typeof gpu.deviceId === 'string' && /^[0-9a-f]{4}$/.test(gpu.deviceId)))) return invalid()
  return value as unknown as SystemInfo
}

let pending: Promise<SystemInfo> | undefined
let cached: { value: SystemInfo; time: number } | undefined

export function getSystemInfo(): Promise<SystemInfo> {
  if (process.platform !== 'linux') return Promise.reject(new Error('系统信息仅支持 Linux 桌面端'))
  if (cached && performance.now() - cached.time < 3000) return Promise.resolve(cached.value)
  if (pending) return pending
  pending = execute(executable, ['--json'], { timeout: 3000, maxBuffer: 64 * 1024, encoding: 'utf8', windowsHide: true })
    .then(({ stdout }) => {
      const value = parseSystemInfo(stdout)
      cached = { value, time: performance.now() }
      return value
    })
    .catch(() => { throw new Error('无法读取系统信息，请检查系统信息服务是否已安装') })
    .finally(() => { pending = undefined })
  return pending
}
