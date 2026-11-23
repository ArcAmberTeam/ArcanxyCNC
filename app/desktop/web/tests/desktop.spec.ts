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
  let closing = false
  let jogging = false
  let powered = false
  let estop = false
  let externalEstop = false
  let commandState = 'idle'
  const snapshot = () => ({
    connected: true, axes: ['X', 'Y', 'Z'], motionMode: 'world', powered, estop,
    linearUnits: 1, angularUnits: 1, commandState,
    capabilities: { 'jog.start': powered && !jogging, 'machine.power-and-home': !estop && !jogging, 'machine.estop': true },
    axisLimits: Object.fromEntries(['X', 'Y', 'Z'].map(name => [name, { maxVelocity: 10 }])),
  })
  const server = net.createServer(socket => {
    sockets.add(socket)
    socket.on('error', (error: NodeJS.ErrnoException) => {
      if (!closing || error.code !== 'ECONNRESET') throw error
    })
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
          if (request.params.action === 'machine.estop') {
            estop = request.params.payload.enabled || externalEstop
            commandState = externalEstop && !request.params.payload.enabled ? 'sent' : 'completed'
            if (estop) powered = false
          }
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
    desktop = await _electron.launch({ args: ['--no-sandbox', '.', '--kiosk', '--socket', socketPath] })
    const page = await desktop.firstWindow()
    if (process.platform === 'linux') {
      expect(await desktop.evaluate(({ app }) => app.isHardwareAccelerationEnabled())).toBe(false)
    }
    expect(await page.evaluate(() => Object.keys(window.cncAdminSudo ?? {}).sort())).toEqual(['enroll', 'maintenanceStatus', 'needsSetup', 'setEnabled', 'setMaintenanceEnabled', 'status'])
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
    const stop = page.getByRole('button', { name: '急停', exact: true })
    const reset = page.getByRole('button', { name: '解除急停', exact: true })
    const resetDialog = page.getByRole('dialog', { name: '确认解除急停' })
    const beforeEstop = commands.length
    await stop.click()
    await expect(reset).toBeEnabled()
    await expect(home).toBeDisabled()
    await reset.click()
    await expect(resetDialog).toContainText('请确认机床无异常')
    await resetDialog.getByRole('button', { name: '取消' }).click()
    expect(commands.slice(beforeEstop)).toEqual([{ action: 'machine.estop', payload: { enabled: true } }])
    await reset.click()
    estop = false
    await expect(resetDialog).toBeHidden()
    await expect(stop).toBeEnabled()
    estop = true
    externalEstop = true
    await reset.click()
    await resetDialog.getByRole('button', { name: '确认解除急停' }).click()
    await expect(page.getByRole('button', { name: '等待复位' })).toBeDisabled()
    commandState = 'unknown'
    const blocked = page.getByRole('dialog', { name: /机床仍处于急停/ })
    await expect(blocked).toContainText('请检查外部急停输入')
    await blocked.getByRole('button', { name: '确定' }).click()
    await expect(reset).toBeEnabled()
    externalEstop = false
    await reset.click()
    await resetDialog.getByRole('button', { name: '确认解除急停' }).click()
    await expect(stop).toBeEnabled()
    expect(commands.slice(beforeEstop)).toEqual([
      { action: 'machine.estop', payload: { enabled: true } },
      { action: 'machine.estop', payload: { enabled: false } },
      { action: 'machine.estop', payload: { enabled: false } },
    ])
    expect(powered).toBe(false)
    expect(commands.some(item => ['machine.power', 'machine.home-all', 'motion.mode'].includes(item.action))).toBe(false)
  } finally {
    closing = true
    await desktop?.close()
    sockets.forEach(socket => socket.destroy())
    await new Promise<void>(resolve => server.close(() => resolve()))
    await rm(folder, { recursive: true, force: true })
  }
})
