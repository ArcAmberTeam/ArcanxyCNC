import { jogAxes, type ActiveAxis, type MachineReadings } from '../bridge.js'

const systems = ['G54', 'G55', 'G56', 'G57', 'G58', 'G59', 'G59.1', 'G59.2', 'G59.3']
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const vector = (value: unknown): value is number[] => Array.isArray(value) && value.length === 9 && value.every(finite)

export function activeAxisSettings(names: string[], data: Record<string, unknown>): ActiveAxis[] {
  const limits = data.axisLimits as Record<string, Record<string, unknown>> | undefined
  return names.map(name => {
    const rotary = 'ABC'.includes(name)
    const units = rotary ? data.angularUnits : data.linearUnits
    const limit = limits?.[name]
    function converted(value: unknown, factor = 1) {
      if (!finite(value) || !finite(units) || units <= 0) return null
      const result = value * factor / units
      return finite(result) ? result : null
    }
    const min = converted(limit?.min)
    const max = converted(limit?.max)
    const maxFeed = converted(limit?.maxVelocity, 60)
    const inverted = min !== null && max !== null && min >= max
    return { name, unit: rotary ? 'deg' : 'mm', min: inverted ? null : min, max: inverted ? null : max,
      maxFeed: maxFeed !== null && maxFeed > 0 ? maxFeed : null }
  })
}

function workPosition(data: Record<string, unknown>): MachineReadings['position'] {
  const { actualPosition, g5xOffset, g92Offset, toolOffset, rotationXY, axes } = data
  if (!Array.isArray(axes) || !vector(actualPosition) || !vector(g5xOffset) || !vector(g92Offset)
    || !vector(toolOffset) || !finite(rotationXY) || data.motionMode !== 'world') return {}
  const relative = actualPosition.map((value, i) => value - g5xOffset[i] - toolOffset[i])
  const angle = -rotationXY * Math.PI / 180
  const [x, y] = relative
  relative[0] = x * Math.cos(angle) - y * Math.sin(angle)
  relative[1] = x * Math.sin(angle) + y * Math.cos(angle)
  const position: MachineReadings['position'] = {}
  for (const axis of jogAxes) {
    const i = 'XYZABCUVW'.indexOf(axis)
    const units = 'ABC'.includes(axis) ? data.angularUnits : data.linearUnits
    if (axes.includes(axis) && finite(units) && units > 0) position[axis] = (relative[i] - g92Offset[i]) / units
  }
  return position
}

export function machineReadings(data: Record<string, unknown>, capabilities: Record<string, unknown>): MachineReadings | null {
  if (data.connected !== true) return null
  const index = data.g5xIndex
  const workSystem = finite(index) && Number.isInteger(index) ? systems[index - 1] ?? null : null
  const feedRatio = finite(data.feedOverride) && data.feedOverride >= 0 ? data.feedOverride : null
  const feedMax = finite(data.feedOverrideMax) && data.feedOverrideMax > 0 ? data.feedOverrideMax : null
  const direction = data.spindleDirection
  const spindleDirection = direction === 0 || direction === 1 || direction === -1 ? direction : null
  const rtcpGeometry: Record<string, number> = {}
  if (data.rtcpGeometry && typeof data.rtcpGeometry === 'object' && finite(data.linearUnits) && data.linearUnits > 0) {
    for (const [key, value] of Object.entries(data.rtcpGeometry)) {
      if (finite(value)) rtcpGeometry[key] = value / data.linearUnits
    }
  }
  const commandRpm = finite(data.spindleSpeed) ? Math.abs(data.spindleSpeed) : null
  return {
    flood: typeof data.flood === 'boolean' ? data.flood : null,
    spindleRpm: finite(data.spindleFeedbackRpm) && data.spindleFeedbackRpm >= 0 ? data.spindleFeedbackRpm : null,
    spindleTarget: commandRpm || (finite(data.defaultSpindleSpeed) && data.defaultSpindleSpeed > 0 ? data.defaultSpindleSpeed : null),
    spindleMin: finite(data.spindleMin) ? data.spindleMin : null,
    spindleMax: finite(data.spindleMax) ? data.spindleMax : null,
    spindleDirection,
    rtcpModel: data.kinematicsModel === 'xyzac-trt-kins' || data.kinematicsModel === 'xyzbc-trt-kins' ? data.kinematicsModel : null,
    rtcpGeometry,
    canForward: capabilities['spindle.forward'] === true && (spindleDirection === 0 || spindleDirection === 1),
    canReverse: capabilities['spindle.reverse'] === true && (spindleDirection === 0 || spindleDirection === -1),
    canStopSpindle: capabilities['spindle.stop'] === true,
    feedRatio, feedMax, workSystem, position: workSystem ? workPosition(data) : {},
    canSetFlood: capabilities['coolant.flood'] === true && typeof data.flood === 'boolean',
    canSetFeed: capabilities['override.feed'] === true && feedRatio !== null && feedMax !== null,
  }
}
