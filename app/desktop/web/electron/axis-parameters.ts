// Transport for the local Rust axis parameter service.
import { createConnection } from 'node:net'
import type { AxisParameterDocument } from '../bridge.js'

export async function axisParameters(count: unknown, edit?: { revision: unknown; changes: unknown }): Promise<AxisParameterDocument> {
  if (count !== 3 && count !== 4 && count !== 5) throw new Error('无效轴方案')
  const request = edit ? { operation: 'save', count, ...edit } : { operation: 'read', count }
  const input = JSON.stringify(request)
  if (Buffer.byteLength(input) > 16384) throw new Error('轴参数请求过大')
  return new Promise((resolve, reject) => {
    const socket = createConnection({ path: '/run/betterlinuxcnc-axis-parameters.sock', allowHalfOpen: true })
    const chunks: Buffer[] = []
    let size = 0
    socket.setTimeout(360000, () => socket.destroy(new Error('轴配置服务超时，请刷新状态')))
    socket.once('connect', () => socket.end(input))
    socket.on('data', (part: Buffer) => {
      size += part.length
      if (size > 32768) socket.destroy(new Error('轴配置服务响应过大'))
      else chunks.push(part)
    })
    socket.once('error', error => reject(new Error('无法访问本机轴配置服务 · ' + error.message)))
    socket.once('end', () => {
      try {
        const doc = JSON.parse(Buffer.concat(chunks).toString('utf8'))
        if (typeof doc?.error === 'string') throw new Error(doc.error)
        if (typeof doc?.revision !== 'string' || !/^[a-f0-9]{64}$/.test(doc.revision)
          || !doc.values || typeof doc.values !== 'object' || Array.isArray(doc.values)
          || !Object.values(doc.values).every(v => typeof v === 'string')) throw new Error('轴配置服务响应无效')
        resolve(doc)
      } catch (err) { reject(err) }
    })
  })
}
