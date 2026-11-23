import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ManualController, type ControlTransport } from './manual-controller.js'
import { RemoteError } from './session.js'

const ready = () => ({
  connected: true, axes: ['X', 'Y', 'Z', 'B', 'C'], powered: true, estop: false,
  motionMode: 'world', linearUnits: 1, angularUnits: 1, commandState: 'idle',
  capabilities: { 'jog.start': true, 'machine.estop': true },
  axisLimits: Object.fromEntries(['X', 'Y', 'Z', 'B', 'C'].map(name => [name, { maxVelocity: 'BC'.includes(name) ? 3 : 10 }])),
})

class Peer implements ControlTransport {
  connected = false
  snapshot = ready()
  requests: Array<{ method: string; params: Record<string, unknown> }> = []
  gate?: Promise<void>
  unknown = false
  private queue: Promise<unknown> = Promise.resolve()
  async connect() { this.connected = true }
  close() { this.connected = false }
  request(method: string, params: Record<string, unknown>, current = () => true) {
    const gate = this.gate
    const task = this.queue.then(async () => {
      if (gate) await gate
      if (!this.connected || !current()) throw new Error('Cancelled')
      this.requests.push({ method, params })
      if (method === 'command.execute') {
        if (this.unknown) { this.close(); throw new RemoteError('result_unknown', 'Unknown command outcome') }
        return { accepted: true, snapshot: structuredClone(this.snapshot) }
      }
      return structuredClone(this.snapshot)
    })
    this.queue = task.catch(() => {})
    return task
  }
}

async function setup() {
  const peer = new Peer()
  let time = 1000
  let focused = true
  const controller = new ManualController(peer, () => time, () => focused, () => {})
  controller.heartbeat()
  await controller.poll()
  return { peer, controller, advance: (ms: number) => { time += ms }, blur: () => { focused = false } }
}

test('linear and rotary feeds use their own machine units and explicit world axes', async () => {
  const { controller, peer } = await setup()
  peer.snapshot.linearUnits = 1 / 25.4
  peer.snapshot.angularUnits = 2
  await controller.poll()
  await controller.start({ axis: 'X', direction: -1, feedRate: 152.4 })
  await controller.stop()
  await controller.poll()
  await controller.start({ axis: 'B', direction: 1, feedRate: 60 })
  const starts = peer.requests.filter(item => item.params.action === 'jog.start')
  const x = starts[0].params.payload as Record<string, unknown>
  assert.ok(Math.abs(Number(x.velocity) - 0.1) < 1e-10)
  assert.equal(x.mode, 'world')
  assert.equal(x.direction, -1)
  assert.deepEqual(starts[1].params.payload, { axis: 'B', direction: 1, mode: 'world', velocity: 2, increment: 0 })
  await controller.stop()
})

test('missing axes, excessive speeds and malformed requests cannot send motion', async () => {
  const { controller, peer } = await setup()
  peer.snapshot.axes = ['X', 'Y', 'Z']
  await controller.poll()
  for (const request of [
    { axis: 'B', direction: 1, feedRate: 30 },
    { axis: 'X', direction: 1, feedRate: 601 },
    { axis: 'X', direction: true, feedRate: 10 },
    { axis: 'X', direction: 1, feedRate: Infinity },
    { axis: 'X', direction: 1, feedRate: 10, joint: 0 },
  ]) await assert.rejects(controller.start(request))
  assert.equal(peer.requests.filter(item => item.method === 'command.execute').length, 0)
})

test('XYZAC readback uses the enabled axes and native angular units until the snapshot expires', async () => {
  const { peer, controller, advance } = await setup()
  peer.snapshot.axes = ['X', 'Y', 'Z', 'A', 'C']
  peer.snapshot.angularUnits = 2
  Object.assign(peer.snapshot.axisLimits, { A: { min: -180, max: 180, maxVelocity: 2 } })
  await controller.poll()
  assert.equal(controller.state.activeAxes?.map(axis => axis.name).join(''), 'XYZAC')
  assert.deepEqual(controller.state.activeAxes?.find(axis => axis.name === 'A'), {
    name: 'A', unit: 'deg', min: -90, max: 90, maxFeed: 60,
  })
  assert.equal(controller.state.axes.B, undefined)
  await controller.start({ axis: 'A', direction: 1, feedRate: 30 })
  assert.deepEqual(peer.requests.at(-1)?.params.payload, { axis: 'A', direction: 1, mode: 'world', velocity: 1, increment: 0 })
  await controller.stop()
  advance(501)
  controller.watchdog()
  assert.equal(controller.state.activeAxes, null)
})

test('joint mode does not guess an axis to joint mapping or switch motion modes', async () => {
  const { controller, peer } = await setup()
  peer.snapshot.motionMode = 'joint'
  await controller.poll()
  await assert.rejects(controller.start({ axis: 'X', direction: 1, feedRate: 100 }))
  assert.equal(controller.state.canJog, false)
  assert.equal(peer.requests.filter(item => item.method === 'command.execute').length, 0)
})

test('release before a queued start is sent revokes it', async () => {
  const { controller, peer } = await setup()
  let release!: () => void
  peer.gate = new Promise<void>(resolve => { release = resolve })
  const start = controller.start({ axis: 'X', direction: 1, feedRate: 100 })
  const rejected = assert.rejects(start)
  const stopped = controller.stop()
  release()
  await Promise.all([rejected, stopped])
  assert.equal(peer.requests.some(item => item.params.action === 'jog.start'), false)
  assert.equal(controller.state.jogging, false)
})

test('loss of focus and expired heartbeat stop jogging without a new status poll', async () => {
  for (const condition of ['focus', 'heartbeat']) {
    const { controller, peer, advance, blur } = await setup()
    await controller.start({ axis: 'C', direction: -1, feedRate: 30 })
    if (condition === 'focus') blur()
    else advance(351)
    controller.watchdog()
    await controller.stop()
    assert.equal(controller.state.jogging, false)
    assert.equal(peer.requests.filter(item => item.params.action === 'jog.stop').length, 1)
    await controller.poll()
    assert.equal(peer.requests.at(-1)?.params.jog_lease, false)
  }
})

test('fresh renderer heartbeats cannot renew jogging with stale machine feedback', async () => {
  const { controller, peer, advance } = await setup()
  await controller.start({ axis: 'Z', direction: 1, feedRate: 100 })
  advance(501)
  controller.heartbeat()
  controller.watchdog()
  await controller.stop()
  assert.equal(controller.state.jogging, false)
  assert.ok(peer.requests.some(item => item.params.action === 'jog.stop'))
})

test('lost command acknowledgement is never replayed after reconnect', async () => {
  const { controller, peer, advance } = await setup()
  peer.unknown = true
  await assert.rejects(controller.start({ axis: 'X', direction: 1, feedRate: 100 }))
  assert.equal(controller.state.commandState, 'unknown')
  peer.unknown = false
  advance(1001)
  controller.heartbeat()
  await controller.poll()
  assert.equal(peer.requests.filter(item => item.params.action === 'jog.start').length, 1)
  assert.equal(controller.state.jogging, false)
  assert.equal(peer.requests.at(-1)?.params.jog_lease, false)
})

test('emergency stop asserts estop explicitly and never toggles it off', async () => {
  const { controller, peer } = await setup()
  await controller.emergencyStop()
  assert.deepEqual(peer.requests.at(-1)?.params, { action: 'machine.estop', payload: { enabled: true } })
})

test('reset requires fresh active estop feedback and waits for readback to change state', async () => {
  const { controller, peer, advance } = await setup()
  await assert.rejects(controller.resetEmergencyStop())
  peer.snapshot.estop = true
  await controller.poll()
  await controller.resetEmergencyStop()
  assert.equal(controller.state.estop, true)
  advance(501)
  controller.heartbeat()
  await assert.rejects(controller.resetEmergencyStop())
  controller.watchdog()
  assert.equal(controller.state.estop, null)
  assert.deepEqual(peer.requests.filter(item => item.method === 'command.execute').map(item => item.params), [
    { action: 'machine.estop', payload: { enabled: false } },
  ])
})

test('closing the window releases the connection and never reconnects', async () => {
  const { controller, peer } = await setup()
  await controller.start({ axis: 'Y', direction: 1, feedRate: 100 })
  const count = peer.requests.length
  controller.close()
  await controller.poll()
  assert.equal(peer.connected, false)
  assert.equal(peer.requests.length, count)
})

test('overview uses rotated work coordinates and sends explicit bounded settings only with fresh feedback', async () => {
  const { controller, peer, advance } = await setup()
  Object.assign(peer.snapshot, {
    g5xIndex: 2, rotationXY: 90, linearUnits: 2, angularUnits: 4,
    actualPosition: [16, 10, 12, 0, 20, 40, 0, 0, 0],
    g5xOffset: [4, 2, 4, 0, 0, 0, 0, 0, 0],
    toolOffset: [2, 2, 2, 0, 0, 0, 0, 0, 0],
    g92Offset: [2, 0, 0, 0, 4, 0, 0, 0, 0],
    flood: false, feedOverride: 1, feedOverrideMax: 1.5,
  })
  Object.assign(peer.snapshot.capabilities, { 'coolant.flood': true, 'override.feed': true })
  await controller.poll()
  const readings = controller.state.readings!
  assert.equal(readings.workSystem, 'G55')
  assert.ok(Math.abs(readings.position.X! - 2) < 1e-10)
  assert.equal(readings.position.Y, -5)
  assert.equal(readings.position.B, 4)
  await controller.setFlood(true)
  await controller.setFeedOverride(1.25)
  await assert.rejects(controller.setFeedOverride(1.51))
  advance(501)
  controller.watchdog()
  assert.equal(controller.state.readings, null)
  await assert.rejects(controller.setFlood(false))
  assert.deepEqual(peer.requests.filter(item => item.method === 'command.execute').map(item => item.params), [
    { action: 'coolant.flood', payload: { enabled: true } },
    { action: 'override.feed', payload: { value: 1.25 } },
  ])
})

test('spindle readback is independent of the target and commands use current limits and direction', async () => {
  const { controller, peer, advance } = await setup()
  Object.assign(peer.snapshot, { spindleSpeed: 800, spindleFeedbackRpm: 731, spindleDirection: 0, spindleMin: 100, spindleMax: 1000 })
  Object.assign(peer.snapshot.capabilities, { 'spindle.forward': true, 'spindle.reverse': true, 'spindle.stop': true })
  await controller.poll()
  assert.equal(controller.state.readings?.spindleRpm, 731)
  assert.equal(controller.state.readings?.spindleTarget, 800)
  await assert.rejects(controller.setSpindle(1, 1200))
  await assert.rejects(controller.setSpindle(-1, NaN))
  await controller.setSpindle(1, 900)
  Object.assign(peer.snapshot, { spindleDirection: 1, spindleFeedbackRpm: null })
  await controller.poll()
  assert.equal(controller.state.readings?.spindleRpm, null)
  await assert.rejects(controller.setSpindle(-1, 900))
  await controller.setSpindle(0)
  Object.assign(peer.snapshot, { spindleDirection: 0, spindleFeedbackRpm: 0 })
  await controller.poll()
  assert.equal(controller.state.readings?.spindleRpm, 0)
  await controller.setSpindle(-1, 700)
  advance(501)
  await assert.rejects(controller.setSpindle(1, 700))
  assert.deepEqual(peer.requests.filter(item => item.method === 'command.execute').map(item => item.params), [
    { action: 'spindle.forward', payload: { speed: 900 } }, { action: 'spindle.stop', payload: {} },
    { action: 'spindle.reverse', payload: { speed: 700 } },
  ])
})
