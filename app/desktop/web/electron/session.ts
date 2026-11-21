import net from 'node:net'
import { lstat } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { tmpdir } from 'node:os'
import { randomUUID } from 'node:crypto'
import validator from 'json-dup-key-validator'

const LIMIT = 65_536
export class RemoteError extends Error {
  constructor(readonly code: string, message: string) { super(message) }
}
export function parseRecord(text: string): Record<string, unknown> {
  const value: unknown = validator.parse(text, false)
  function valid(item: unknown, depth = 0): boolean {
    if (depth > 64) return false
    if (typeof item === 'number') return Number.isFinite(item)
    if (item && typeof item === 'object') return Object.values(item).every(child => valid(child, depth + 1))
    return true
  }
  if (!value || Array.isArray(value) || typeof value !== 'object' || !valid(value)) throw new Error('Invalid JSON record')
  return value as Record<string, unknown>
}
export const defaultSocket = () => join(process.env.XDG_RUNTIME_DIR || tmpdir(), 'betterlinuxcnc/control.sock')

// BEGIN: ControllerSession
// One serialized owner connection. Disconnect invalidates queued work; nothing replays.
export class ControllerSession {
  private socket?: net.Socket
  private bytes: Buffer = Buffer.alloc(0)
  private pending?: { id: string; method: string; resolve: (value: Record<string, unknown>) => void; reject: (error: Error) => void; timer: NodeJS.Timeout }
  private queue: Promise<unknown> = Promise.resolve()
  private epoch = 0
  private queued = 0
  constructor(readonly path = defaultSocket(), readonly ini?: string) {}
  get connected() { return !!this.socket && !this.socket.destroyed }
  async connect(attach = true) {
    this.close()
    const generation = this.epoch
    const [directory, endpoint] = await Promise.all([lstat(dirname(this.path)), lstat(this.path)])
    if (generation !== this.epoch) throw new Error('连接已取消')
    const uid = process.getuid?.()
    if (uid === undefined || !directory.isDirectory() || directory.uid !== uid || (directory.mode & 0o077)
      || !endpoint.isSocket() || endpoint.uid !== uid || (endpoint.mode & 0o077)) throw new Error('本地服务 socket 的所有者或私有权限不正确')
    const socket = net.createConnection(this.path)
    this.socket = socket
    socket.on('data', chunk => { if (this.socket === socket) this.receive(chunk) })
    socket.on('error', error => { if (this.socket === socket) this.fail(error) })
    socket.on('close', () => { if (this.socket === socket) this.fail(new Error('本地服务连接中断')) })
    await new Promise<void>((resolve, reject) => {
      const deadline = setTimeout(() => { this.close(); reject(new Error('连接本地服务超时')) }, 2000)
      socket.once('connect', () => { clearTimeout(deadline); resolve() })
      socket.once('error', error => { clearTimeout(deadline); reject(error) })
      socket.once('close', () => { clearTimeout(deadline); reject(new Error('连接已关闭')) })
    })
    if (generation !== this.epoch) throw new Error('连接已取消')
    if (attach) {
      try { await this.request('session.attach', this.ini ? { ini_path: this.ini } : {}) }
      catch (error) { this.close(); throw error }
    }
  }
  close() {
    this.epoch++
    const socket = this.socket; this.socket = undefined; socket?.destroy()
    this.bytes = Buffer.alloc(0)
    const pending = this.pending; this.pending = undefined
    if (pending) {
      clearTimeout(pending.timer)
      pending.reject(new RemoteError(pending.method === 'command.execute' ? 'result_unknown' : 'disconnected',
        pending.method === 'command.execute' ? '命令结果未知，已断开且不会自动重发' : '本地服务连接中断'))
    }
  }
  private fail(_error: Error) { this.close() }
  request(method: string, params: Record<string, unknown>, current: () => boolean = () => true): Promise<Record<string, unknown>> {
    if (this.queued >= 32) return Promise.reject(new Error('本地请求队列已满'))
    const epoch = this.epoch
    this.queued++
    const task = this.queue.then(() => {
      if (epoch !== this.epoch || !this.connected || !current()) throw new Error('请求已取消或本地控制服务尚未连接')
      const id = randomUUID(), payload = Buffer.from(JSON.stringify({ version: 2, request_id: id, method, params }))
      if (!payload.length || payload.length > LIMIT) throw new Error('本地服务请求超过报文大小限制')
      return new Promise<Record<string, unknown>>((resolve, reject) => {
        const timer = setTimeout(() => this.fail(new Error('服务响应超时')), method === 'command.execute' ? 8000 : 2000)
        this.pending = { id, method, resolve, reject, timer }
        const header = Buffer.alloc(4); header.writeUInt32BE(payload.length)
        this.socket!.write(Buffer.concat([header, payload]))
      })
    }).finally(() => { this.queued-- })
    this.queue = task.catch(() => {})
    return task
  }
  private receive(chunk: Buffer) {
    this.bytes = Buffer.concat([this.bytes, chunk])
    if (this.bytes.length > LIMIT + 4) { this.close(); return }
    if (this.bytes.length < 4) return
    const size = this.bytes.readUInt32BE()
    if (!size || size > LIMIT) { this.close(); return }
    if (this.bytes.length < size + 4) return
    try {
      if (this.bytes.length !== size + 4) throw new Error('Unexpected response bytes')
      const record = parseRecord(new TextDecoder('utf-8', { fatal: true }).decode(this.bytes.subarray(4)))
      this.bytes = Buffer.alloc(0)
      const pending = this.pending
      const keys = Object.keys(record).sort().join(',')
      if (!pending || record.version !== 2 || record.request_id !== pending.id || !['request_id,result,version', 'error,request_id,version'].includes(keys)) throw new Error('本地控制服务协议不匹配')
      const result = record.result, problem = record.error as Record<string, unknown> | undefined
      if (problem) {
        if (Array.isArray(problem) || Object.keys(problem).sort().join(',') !== 'code,message' || typeof problem.code !== 'string' || typeof problem.message !== 'string') throw new Error('Invalid remote error')
        clearTimeout(pending.timer); this.pending = undefined
        pending.reject(new RemoteError(problem.code, problem.message))
      } else {
        if (!result || Array.isArray(result) || typeof result !== 'object') throw new Error('Invalid service result')
        clearTimeout(pending.timer); this.pending = undefined; pending.resolve(result as Record<string, unknown>)
      }
    } catch (error) { this.fail(error as Error) }
  }
}
// END: ControllerSession
