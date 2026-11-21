// Loopback development adapter for the unprivileged Rust preset editor.
import { execFile } from 'node:child_process'
import { constants, accessSync } from 'node:fs'
import { open } from 'node:fs/promises'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { profileLayouts, type AxisCount } from '../bridge.ts'
import { fileURLToPath } from 'node:url'
import type { Plugin } from 'vite'

// Read the on-disk preset on each request, including edits from a previous helper installation.
async function readPreset(count: AxisCount) {
  const name = `axis-${count}.ini`
  let file
  try {
    file = await open(join(homedir(), '.local/share/betterlinuxcnc/axis-preview', name), constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK)
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
    file = await open(new URL(`../../../../tools/appliance/templates/${name}`, import.meta.url), 'r')
  }
  let text: string
  try {
    const stat = await file.stat()
    if (!stat.isFile() || stat.size > 65536) throw new Error('轴配置文件无效')
    text = await file.readFile('utf8')
  } finally { await file.close() }

  const sections: Record<string, Map<string, string>> = Object.create(null)
  let group: Map<string, string> | undefined
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.split(/[;#]/, 1)[0].trim()
    if (line.startsWith('[') && line.endsWith(']')) {
      group = sections[line.slice(1, -1).toUpperCase()] ??= new Map()
    } else {
      const eq = line.indexOf('=')
      if (eq > 0) group?.set(line.slice(0, eq).trim().toUpperCase(), line.slice(eq + 1).trim())
    }
  }
  const layout = sections.TRAJ?.get('COORDINATES')?.replace(/\s/g, '')
  if (!layout || (layout !== profileLayouts[count] && !(count === 5 && layout === 'XYZBC'))
    || Number(sections.KINS?.get('JOINTS')) !== count) throw new Error('轴方案与 INI 不匹配')
  const values: Record<string, string> = { axes: layout }
  const model = sections.KINS?.get('KINEMATICS')?.split(/\s+/)[0]
  if (model) values.model = model
  for (const [i, axis] of [...layout].entries()) {
    const a = sections['AXIS_' + axis]
    const j = sections['JOINT_' + i]
    const rotary = 'ABC'.includes(axis)
    values[axis + '.joint'] = String(i)
    const fields = {
      min: a?.get('MIN_LIMIT'), max: a?.get('MAX_LIMIT'), acceleration: a?.get('MAX_ACCELERATION'),
      estimatedTravel: a?.get('ESTIMATED_TRAVEL'),
      measuredTravel: rotary ? a?.get('MEASURED_TRAVEL_DEG') : sections.BETTERCNC_HOMING?.get('TRAVEL_' + axis + '_MM'),
      homeSequence: j?.get('HOME_SEQUENCE'), homeOffset: j?.get('HOME_OFFSET'), ratio: a?.get('TRANSMISSION_RATIO'),
      mechanicalZero: a?.get('MECHANICAL_ZERO'), angleMin: rotary ? j?.get('MIN_LIMIT') : undefined,
      angleMax: rotary ? j?.get('MAX_LIMIT') : undefined,
    }
    for (const [key, value] of Object.entries(fields)) if (value !== undefined) values[axis + '.' + key] = value
    if (a?.has('MAX_VELOCITY')) values[axis + '.maxFeed'] = String(Number(a.get('MAX_VELOCITY')) * 60)
    if (j?.has('STEP_SCALE')) {
      const scale = Number(j.get('STEP_SCALE'))
      values[axis + '.scale'] = String(Math.abs(scale))
      values[axis + '.direction'] = scale < 0 ? 'negative' : 'positive'
    }
    if (j && ['HOME', 'HOME_OFFSET', 'HOME_SEQUENCE', 'HOME_SEARCH_VEL', 'HOME_ABSOLUTE_ENCODER'].some(key => j.has(key))) {
      const useIndex = ['1', 'TRUE', 'YES'].includes(j.get('HOME_USE_INDEX')?.toUpperCase() ?? '')
      const search = Number(j.get('HOME_SEARCH_VEL') ?? 0) !== 0
      values[axis + '.homing'] = ['1', '2'].includes(j.get('HOME_ABSOLUTE_ENCODER') ?? '') ? 'absolute'
        : search ? (useIndex ? 'switch-index' : 'switch') : (useIndex ? 'index' : 'manual')
    }
  }
  return { values, revision: createHash('sha256').update(text).digest('hex') }
}

export function axisPreview(): Plugin {
  const candidates = [
    process.env.BETTERCNC_PREVIEW_HELPER,
    fileURLToPath(new URL('../../../platform/configuration/manage-ini/target/release/pa-config', import.meta.url)),
    '/usr/lib/betterlinuxcnc/manage-ini/pa-config',
  ]
  const helper = candidates.find((path): path is string => {
    if (!path) return false
    try { accessSync(path, constants.X_OK); return true } catch { return false }
  })
  return {
    name: 'local-axis-preset-files',
    config: (_, env) => ({ define: {
      __AXIS_PREVIEW_FILES__: JSON.stringify(env.command === 'serve' && !!helper),
    } }),
    configureServer(server) {
      server.middlewares.use('/__axis-presets', async (req, res) => {
        res.setHeader('Content-Type', 'application/json')
        res.setHeader('Cache-Control', 'no-store')
        const host = req.headers.host ?? ''
        if (!/^(localhost|127\.0\.0\.1|\[::1\])(:[0-9]+)?$/.test(host)
          || !['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.socket.remoteAddress ?? '')
          || req.headers.origin !== 'http://' + host || req.method !== 'POST'
          || req.headers['content-type'] !== 'application/json') {
          res.statusCode = 403
          res.end('{}')
          return
        }
        try {
          const chunks: Buffer[] = []
          let size = 0
          for await (const chunk of req) {
            const bytes = Buffer.from(chunk)
            size += bytes.length
            if (size > 16384) throw new Error('轴参数请求过大')
            chunks.push(bytes)
          }
          const body = Buffer.concat(chunks)
          if (!helper) {
            const { operation, count } = JSON.parse(body.toString('utf8'))
            if (operation !== 'read' || (count !== 3 && count !== 4 && count !== 5)) throw new Error('本机只支持读取轴配置')
            res.end(JSON.stringify(await readPreset(count)))
            return
          }
          const child = execFile(helper, ['preview-parameters'], { timeout: 5000, maxBuffer: 32768 }, (error, stdout) => {
            if (error) res.statusCode = 503
            res.end(error ? JSON.stringify({ error: '本机 Rust 配置服务不可用' }) : stdout)
          })
          child.stdin?.on('error', () => { /* The exit callback reports the failure. */ })
          child.stdin?.end(body)
        } catch (error) {
          res.statusCode = 400
          res.end(JSON.stringify({ error: String(error) }))
        }
      })
    },
  }
}
