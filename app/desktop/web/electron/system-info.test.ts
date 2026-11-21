import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseSystemInfo } from './system-info.js'

const snapshot = () => ({
  schemaVersion: 1,
  cpu: { model: 'Test CPU', logicalCores: 8 },
  gpus: [{ model: 'Test GPU', vendorId: '1234', deviceId: '0001', driver: null }],
  memory: { totalBytes: 8192, availableBytes: 0 },
  kernel: '6.12-test',
})

test('system information preserves zero available memory and unknown sections', () => {
  assert.deepEqual(parseSystemInfo(JSON.stringify(snapshot())), snapshot())
  const unavailable = { schemaVersion: 1, cpu: null, gpus: null, memory: null, kernel: null }
  assert.deepEqual(parseSystemInfo(JSON.stringify(unavailable)), unavailable)
  assert.deepEqual(parseSystemInfo(JSON.stringify({ ...snapshot(), gpus: [] })).gpus, [])
})

test('system information rejects invalid or incompatible helper responses', () => {
  for (const patch of [
    { schemaVersion: 2 }, { cpu: {} }, { cpu: { model: null, logicalCores: 0 } },
    { memory: { totalBytes: 8192, availableBytes: 8193 } },
    { memory: { totalBytes: -1, availableBytes: null } },
    { memory: { totalBytes: 8192, availableBytes: -1 } },
    { memory: { totalBytes: Number.MAX_SAFE_INTEGER + 1, availableBytes: null } },
    { gpus: [{}] }, { gpus: Array(33).fill(snapshot().gpus[0]) },
    { kernel: '' }, { kernel: 'x'.repeat(1025) },
  ]) assert.throws(() => parseSystemInfo(JSON.stringify({ ...snapshot(), ...patch })))
  for (const raw of ['null', '[]', '{}', '{invalid']) assert.throws(() => parseSystemInfo(raw))
})
