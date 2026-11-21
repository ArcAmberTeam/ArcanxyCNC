import { test } from 'node:test'
import assert from 'node:assert/strict'
import net from 'node:net'
import { mkdtemp, chmod, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { ControllerSession, parseRecord, RemoteError } from './session.js'

async function peer(reply: (request: any, socket: net.Socket) => void) {
  const folder = await mkdtemp(join(tmpdir(), 'cnc-session-'))
  const path = join(folder, 'control.sock'), requests: any[] = []
  const server = net.createServer(socket => {
    let buffer: Buffer = Buffer.alloc(0)
    socket.on('data', data => {
      buffer = Buffer.concat([buffer, data])
      while (buffer.length >= 4 && buffer.length >= buffer.readUInt32BE() + 4) {
        const size = buffer.readUInt32BE(), request = JSON.parse(buffer.subarray(4, 4 + size).toString())
        buffer = buffer.subarray(4 + size); requests.push(request); reply(request, socket)
      }
    })
  })
  await new Promise<void>(resolve => server.listen(path, resolve)); await chmod(path, 0o600)
  return { path, requests, close: async () => { await new Promise<void>(resolve => server.close(() => resolve())); await rm(folder, { recursive: true }) } }
}
function respond(socket: net.Socket, request: any, result: unknown) {
  const data = Buffer.from(JSON.stringify({ version: 2, request_id: request.request_id, result }))
  const header = Buffer.alloc(4); header.writeUInt32BE(data.length)
  socket.write(header.subarray(0, 2)); socket.write(Buffer.concat([header.subarray(2), data]))
}
test('reject duplicate fields and non-finite values', () => {
  assert.throws(() => parseRecord('{"value": 1, "value": 2}'))
  assert.throws(() => parseRecord('{"value": 1e999}'))
})
test('framing survives fragmented responses and read-only queries never attach', async () => {
  const server = await peer((request, socket) => respond(socket, request, { connected: false }))
  const client = new ControllerSession(server.path)
  try { await client.connect(false); assert.equal((await client.request('machine.status', {})).connected, false); assert.deepEqual(server.requests.map(value => value.method), ['machine.status']) }
  finally { client.close(); await server.close() }
})
test('lost command acknowledgement is unknown and never replayed', async () => {
  const server = await peer((request, socket) => request.method === 'command.execute' ? socket.end() : respond(socket, request, {}))
  const client = new ControllerSession(server.path)
  try {
    await client.connect()
    await assert.rejects(client.request('command.execute', { action: 'program.pause', payload: {} }), error => error instanceof RemoteError && error.code === 'result_unknown')
    assert.equal(client.connected, false)
    assert.equal(server.requests.filter(value => value.method === 'command.execute').length, 1)
  } finally { client.close(); await server.close() }
})
test('insecure endpoints are refused before any request', async () => {
  const server = await peer((request, socket) => respond(socket, request, {}))
  const client = new ControllerSession(server.path)
  try { await chmod(server.path, 0o666); await assert.rejects(client.connect()); assert.equal(server.requests.length, 0) }
  finally { client.close(); await server.close() }
})
