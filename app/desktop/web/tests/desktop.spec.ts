import { test, expect, _electron } from '@playwright/test'
import net from 'node:net'
import { mkdtemp, chmod, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

test('sandboxed desktop bridge sends real framed requests and stops on release and blur', async () => {
  const folder = await mkdtemp(join(tmpdir(), 'cnc-desktop-'))
  const socketPath = join(folder, 'control.sock')
  const commands: Array<{ action: string; payload: Record<string, unknown> }> = []
  const sockets = new Set<net.Socket>()
  let jogging = false
  let powered = false
  const snapshot = () => ({
    connected: true, axes: ['X', 'Y', 'Z'], motionMode: 'world', powered, estop: false,
    linearUnits: 1, angularUnits: 1, commandState: 'idle',
    capabilities: { 'jog.start': powered && !jogging, 'machine.power-and-home': !jogging, 'machine.estop': true },
    axisLimits: Object.fromEntries(['X', 'Y', 'Z'].map(name => [name, { maxVelocity: 10 }])),
  })
  const server = net.createServer(socket => {
    sockets.add(socket)
    socket.on('close', () => sockets.delete(socket))
    let bytes: Buffer = Buffer.alloc(0)
    socket.on('data', chunk => {
      bytes = Buffer.concat([bytes, chunk])
      while (bytes.length >= 4 && bytes.length >= bytes.readUInt32BE() + 4) {
        const size = bytes.readUInt32BE()
        const request = JSON.parse(bytes.subarray(4, size + 4).toString())
        bytes = bytes.subarray(size + 4)
        let result: unknown = snapshot()
        if (request.method === 'command.execute') {
          commands.push(request.params)
          if (request.params.action === 'machine.power-and-home') powered = true
          if (request.params.action === 'jog.start') jogging = true
          if (['jog.stop', 'machine.estop'].includes(request.params.action)) jogging = false
          result = { accepted: true, snapshot: snapshot() }
        }
        const body = Buffer.from(JSON.stringify({ version: 2, request_id: request.request_id, result }))
        const header = Buffer.alloc(4)
        header.writeUInt32BE(body.length)
        socket.write(Buffer.concat([header, body]))
      }
    })
  })
  await new Promise<void>(resolve => server.listen(socketPath, resolve))
  await chmod(socketPath, 0o600)
  let desktop: Awaited<ReturnType<typeof _electron.launch>> | undefined
  try {
    desktop = await _electron.launch({ args: ['--no-sandbox', '.', '--socket', socketPath] })
    const page = await desktop.firstWindow()
    expect(await page.evaluate(() => Object.keys(window.cncAdminSudo ?? {}).sort())).toEqual(['enroll', 'needsSetup', 'setEnabled', 'status'])
    await expect(page.evaluate(() => window.cncAdminSudo!.setEnabled(true, ''))).rejects.toThrow('管理员密码')
    await page.bringToFront()
    await page.getByRole('button', { name: '控制', exact: true }).click()
    await page.getByRole('button', { name: /^移动控制/ }).click()
    const home = page.getByRole('button', { name: '回零', exact: true })
    const confirmation = page.getByRole('dialog', { name: '确认回零' })
    await home.click()
    await expect(confirmation).toBeVisible()
    await confirmation.getByRole('button', { name: '取消' }).click()
    expect(commands).toEqual([])
    await home.click()
    await confirmation.getByRole('button', { name: '确认无遮挡并回零' }).click()
    await expect.poll(() => commands.slice()).toEqual([
      { action: 'machine.power-and-home', payload: { clearanceConfirmed: true } },
    ])
    const button = page.getByRole('button', { name: 'X 轴正向' })
    await expect(button).toBeEnabled()
    await expect(page.getByRole('button', { name: 'B 轴正向' })).toHaveCount(0)
    await button.focus()
    await page.keyboard.down('Space')
    await expect.poll(() => commands.filter(item => item.action === 'jog.start').length).toBe(1)
    expect(commands.find(item => item.action === 'jog.start')?.payload).toEqual({
      axis: 'X', direction: 1, mode: 'world', velocity: 100 / 60, increment: 0,
    })
    await page.keyboard.up('Space')
    await expect.poll(() => jogging).toBe(false)
    await expect(button).toBeEnabled()
    await button.focus()
    await expect(button).toBeFocused()
    await page.keyboard.down('Space')
    await expect.poll(() => commands.filter(item => item.action === 'jog.start').length).toBe(2)
    await desktop.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].blur())
    await expect.poll(() => jogging).toBe(false)
    await page.keyboard.up('Space')
    await page.bringToFront()
    await page.getByRole('button', { name: '急停', exact: true }).click()
    await expect.poll(() => commands.some(item => item.action === 'machine.estop')).toBe(true)
    expect(commands.find(item => item.action === 'machine.estop')?.payload).toEqual({ enabled: true })
    expect(commands.some(item => ['machine.power', 'machine.home-all', 'motion.mode'].includes(item.action))).toBe(false)
  } finally {
    await desktop?.close()
    sockets.forEach(socket => socket.destroy())
    await new Promise<void>(resolve => server.close(() => resolve()))
    await rm(folder, { recursive: true, force: true })
  }
})
