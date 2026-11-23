import { test, expect, type Page } from '@playwright/test'
import type { AxisCount, AxisOperation, AxisProfileStatus } from '../bridge'

async function connect(page: Page, axes = ['X', 'Y', 'Z', 'B', 'C'], overview = false) {
  await page.addInitScript(enabledAxes => {
    const calls: unknown[] = []
    const listeners = new Set<(state: unknown) => void>()
    let state = {
      serviceConnected: true, connected: true, canJog: true, canEstop: true, estop: false, jogging: false,
      axes: Object.fromEntries(enabledAxes.map(axis => [axis, { maxFeed: 600, unit: 'ABC'.includes(axis) ? 'deg' : 'mm' }])),
      activeAxes: enabledAxes.map(name => ({ name, unit: 'ABC'.includes(name) ? 'deg' : 'mm',
        min: name === 'X' ? 0 : -10, max: name === 'X' ? null : 10, maxFeed: 600 })),
      readings: { spindleRpm: 784, spindleTarget: 800, spindleDirection: 0, spindleMin: 100, spindleMax: 3000,
        canForward: true, canReverse: true, canStopSpindle: true, flood: false, canSetFlood: true,
        feedRatio: 1, feedMax: 1.5, canSetFeed: true, workSystem: 'G54', rtcpModel: null, rtcpGeometry: {},
        position: Object.fromEntries(enabledAxes.map((axis, i) => [axis, i * 10])) },
      reason: '', error: '', commandState: 'idle',
    }
    function publish(jogging: boolean) {
      state = { ...state, jogging, canJog: !jogging }
      listeners.forEach(listener => listener(state))
    }
    Object.assign(window, {
      controlTestCalls: calls,
      cncControl: {
        getState: async () => state,
        onState: (listener: (state: unknown) => void) => { listeners.add(listener); return () => listeners.delete(listener) },
        startJog: async (request: unknown) => { calls.push(request); publish(true) },
        stopJog: () => { calls.push('stop'); publish(false) },
        setSpindle: async (direction: number, rpm?: number) => { calls.push({ direction, rpm }) },
        setFlood: async (enabled: boolean) => { calls.push({ enabled }) },
        setFeedOverride: async (ratio: number) => { calls.push({ ratio }) },
        heartbeat: () => {},
        emergencyStop: async () => { calls.push('estop') },
      },
    })
  }, axes)
  await page.goto('/')
  await page.getByRole('button', { name: '控制', exact: true }).click()
  if (!overview) await page.getByRole('button', { name: /^移动控制/ }).click()
}

test('manual overview fits its cards to the frame and gives spare height to coordinates', async ({ page }) => {
  await page.setViewportSize({ width: 1152, height: 864 })
  await connect(page, ['X', 'Y', 'Z', 'B', 'C'], true)
  const spindle = page.locator('section.readout').filter({ has: page.getByRole('heading', { name: '主轴' }) })
  const coordinates = page.locator('section.readout').filter({ has: page.getByRole('heading', { name: '工件坐标' }) })
  const motion = page.getByRole('button', { name: '移动控制', exact: true })
  const axes = page.getByRole('button', { name: '轴配置', exact: true })
  for (const card of [spindle, coordinates, motion, axes]) {
    await expect(card).toHaveCSS('padding', '12px 18px')
    await expect(card).toHaveCSS('border-radius', '25px')
    await expect(card).toHaveCSS('background-color', 'rgba(255, 255, 255, 0.78)')
  }
  const shortHeight = (await coordinates.boundingBox())!.height
  await page.setViewportSize({ width: 1152, height: 1200 })
  expect((await coordinates.boundingBox())!.height).toBeGreaterThan(shortHeight)
  const frame = (await page.getByRole('region', { name: '手动控制' }).boundingBox())!
  const first = (await spindle.boundingBox())!
  const last = (await axes.boundingBox())!
  expect(first.x - frame.x).toBeCloseTo(7, 0)
  expect(first.y - frame.y).toBeCloseTo(7, 0)
  expect(frame.y + frame.height - last.y - last.height).toBeCloseTo(7, 0)
  const rows = coordinates.locator('dl > div')
  for (const row of await rows.all()) {
    await expect(row).toHaveCSS('border-top-width', '0px')
    await expect(row).toHaveCSS('border-bottom-width', '0px')
  }
  expect((await rows.first().boundingBox())!.height).toBeLessThanOrEqual(56)
})

test('browser preview stays offline', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('-')
  await page.getByRole('button', { name: '启动', exact: true }).click()
  const prompt = page.getByRole('dialog', { name: '请先选择加工程序' })
  await expect(prompt).toBeVisible()
  await prompt.getByRole('button', { name: '确定' }).click()
  const illustration = page.getByRole('img', { name: '五轴机床示意图' })
  await expect(illustration).toHaveCount(0)
  await page.getByRole('button', { name: '控制', exact: true }).click()
  await expect(illustration).toBeVisible()
  await expect(page.getByRole('button', { name: 'X 轴正向' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '主轴' })).toBeVisible()
  await expect(page.getByLabel('主轴反馈转速')).toHaveText('- RPM')
  await expect(page.getByRole('button', { name: '正转', exact: true })).toBeDisabled()
  await expect(page.getByRole('switch', { name: '冷却系统' })).toBeDisabled()
  await expect(page.getByRole('slider', { name: '进给倍率' })).toBeDisabled()
  await expect(page.getByRole('heading', { name: '工件坐标' })).toBeVisible()
  await expect(page.getByRole('button', { name: '移动控制', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: '轴配置', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: '急停', exact: true })).toBeDisabled()
})

test('manual spindle and coolant controls use explicit operator input', async ({ page }) => {
  await connect(page, ['X', 'Y', 'Z'], true)
  await expect(page.getByLabel('主轴反馈转速')).toContainText('784')
  const input = page.getByRole('spinbutton', { name: '目标 RPM' })
  await expect(input).toHaveValue('800')
  await input.fill('900')
  const calls = () => page.evaluate(() => (window as unknown as { controlTestCalls: unknown[] }).controlTestCalls)
  expect(await calls()).not.toContainEqual({ direction: 1, rpm: 900 })
  await page.getByRole('button', { name: '正转', exact: true }).click()
  await page.getByRole('button', { name: '停止主轴' }).click()
  await page.getByRole('switch', { name: '冷却系统' }).click()
  expect(await calls()).toContainEqual({ direction: 1, rpm: 900 })
  expect(await calls()).toContainEqual(expect.objectContaining({ direction: 0 }))
  expect(await calls()).toContainEqual({ enabled: true })
})

test('axis directions map to the requested controls and mouse release stops', async ({ page }) => {
  await connect(page)
  for (const [axis, direction, label] of [
    ['X', -1, 'X 轴负向'], ['Y', 1, 'Y 轴正向'], ['Z', -1, 'Z 轴负向'], ['B', 1, 'B 轴正向'], ['C', -1, 'C 轴负向'],
  ] as const) {
    const button = page.getByRole('button', { name: label })
    const box = await button.boundingBox()
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2)
    await page.mouse.down()
    await expect(button).toHaveAttribute('aria-pressed', 'true')
    await page.mouse.up()
    await expect(button).toHaveAttribute('aria-pressed', 'false')
    const calls = await page.evaluate(() => (window as unknown as { controlTestCalls: unknown[] }).controlTestCalls)
    expect(calls).toContainEqual({ axis, direction, feedRate: 'BC'.includes(axis) ? 30 : 100 })
    expect(calls.at(-1)).toBe('stop')
  }
})

test('dragging out, keyboard release, and switching sections cancel a hold', async ({ page }) => {
  await connect(page)
  const button = page.getByRole('button', { name: 'X 轴正向' })
  const box = await button.boundingBox()
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2)
  await page.mouse.down()
  await page.mouse.move(box!.x + box!.width + 20, box!.y)
  await expect(button).toHaveAttribute('aria-pressed', 'false')
  await page.mouse.up()
  await button.focus()
  await page.keyboard.down('Space')
  await expect(button).toHaveAttribute('aria-pressed', 'true')
  await page.keyboard.up('Space')
  await expect(button).toHaveAttribute('aria-pressed', 'false')
  await page.keyboard.down('Enter')
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.keyboard.up('Enter')
  const calls = await page.evaluate(() => (window as unknown as { controlTestCalls: unknown[] }).controlTestCalls)
  expect(calls.at(-1)).toBe('stop')
})

test('three-axis machines omit rotary controls and estop is wired', async ({ page }) => {
  await connect(page, ['X', 'Y', 'Z'])
  await expect(page.getByRole('button', { name: 'B 轴正向' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'C 轴负向' })).toHaveCount(0)
  await page.getByRole('button', { name: '急停', exact: true }).click()
  const calls = await page.evaluate(() => (window as unknown as { controlTestCalls: unknown[] }).controlTestCalls)
  expect(calls).toContain('estop')
})

test('axis configuration keeps written profiles separate from controller feedback', async ({ page }) => {
  await page.addInitScript(() => {
    const requests: AxisCount[] = []
    Object.assign(window, { profileRequests: requests })
    const status: AxisProfileStatus = {
      profiles: [
        { axis_count: 3, axes: 'XYZ', available: true, reason: '' },
        { axis_count: 4, axes: 'XYZC', available: false, reason: '缺少旋转轴参数' },
        { axis_count: 5, axes: 'XYZAC', available: true, reason: '' },
      ], configured_axis_count: 3, operation: null,
    }
    const documents: Record<AxisCount, Record<string, string>> = {
      3: { 'X.min': '0', 'X.maxFeed': '300' }, 4: {}, 5: { 'A.maxFeed': '75' },
    }
    window.cncAxisProfiles = {
      read: async count => ({ revision: 'initial', values: { ...documents[count] } }),
      save: async (count, revision, changes) => {
        if (revision !== 'initial' || count !== 5) throw new Error('方案版本错误')
        Object.assign(documents[count], changes)
        return { revision: 'saved', values: { ...documents[count] } }
      },
      status: async () => structuredClone(status),
      request: async count => {
        requests.push(count)
        const accepted: AxisOperation = { phase: 'scheduled', axis_count: count, started_at: 1, message: '' }
        status.operation = accepted
        return accepted
      },
    }
    Object.assign(window, { finishProfile: () => {
      status.configured_axis_count = 5
      status.operation = { ...status.operation!, phase: 'configured' }
    } })
  })
  await connect(page, ['X', 'Y', 'Z'])
  await page.getByRole('button', { name: '轴配置', exact: true }).click()
  const parameters = page.getByRole('table', { name: '轴参数', exact: true })
  await expect(parameters.getByRole('spinbutton', { name: 'X 软限位下限' })).toHaveValue('0')
  await expect(parameters.getByRole('spinbutton', { name: 'X 软限位上限' })).toHaveValue('')
  await expect(parameters.getByRole('spinbutton', { name: 'X 最大速度' })).toHaveValue('300')
  const picker = page.getByRole('button', { name: /^轴方案/ })
  await expect(picker).toContainText('三轴')
  await picker.click()
  await expect(page.getByRole('menuitemradio', { name: /三轴/ })).toBeChecked()
  await expect(page.getByRole('menuitemradio', { name: /四轴/ })).toBeEnabled()
  await expect(page.getByRole('menuitemradio', { name: /四轴/ })).toHaveAccessibleDescription('缺少旋转轴参数')
  await page.getByRole('menuitemradio', { name: /五轴/ }).click()
  await expect(picker).toContainText('五轴 · XYZAC')
  await expect(page.getByRole('menu')).toHaveCount(0)
  const requests = () => page.evaluate(() => (window as unknown as { profileRequests: number[] }).profileRequests)
  expect(await requests()).toEqual([5])
  const save = page.getByRole('button', { name: '保存参数', exact: true })
  await expect(save).toBeDisabled()
  await expect(page.getByRole('status')).toHaveText('五轴方案已提交，等待切换。')
  await page.evaluate(() => (window as unknown as { finishProfile(): void }).finishProfile())
  await expect(page.getByRole('status')).toHaveText('五轴方案已写入。')
  await expect(parameters.getByRole('rowheader')).toHaveText(['X', 'Y', 'Z', 'A', 'C'])
  const velocity = parameters.getByRole('spinbutton', { name: 'A 最大速度' })
  await expect(velocity).toHaveValue('75')
  const travel = parameters.getByRole('spinbutton', { name: 'A 实测行程' })
  await travel.fill('0')
  await save.click()
  await expect(page.getByRole('alert')).toContainText('A 实测行程')
  await travel.fill('180')
  await velocity.fill('90')
  await save.click()
  await expect(page.getByText('轴参数已保存', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '刷新状态' }).click()
  await expect(velocity).toHaveValue('90')
  await expect(travel).toHaveValue('180')
  await page.getByRole('button', { name: '返回移动控制' }).click()
  await expect(page.getByRole('button', { name: 'A 轴正向' })).toHaveCount(0)
  expect(await requests()).toEqual([5])
})

test('the XYZAC profile exposes A and C jog controls', async ({ page }) => {
  await connect(page, ['X', 'Y', 'Z', 'A', 'C'])
  const a = page.getByRole('button', { name: 'A 轴正向' })
  await a.focus()
  await page.keyboard.press('Space')
  await expect(page.getByRole('button', { name: 'C 轴负向' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'B 轴正向' })).toHaveCount(0)
  const calls = await page.evaluate(() => (window as unknown as { controlTestCalls: unknown[] }).controlTestCalls)
  expect(calls).toContainEqual({ axis: 'A', direction: 1, feedRate: 30 })
})

test('a failed profile status read disables applying and can be refreshed', async ({ page }) => {
  await page.addInitScript(() => {
    let reads = 0
    window.cncAxisProfiles = {
      read: async () => ({revision: 'v1', values: {}}),
      save: async () => { throw new Error('不应保存配置') },
      status: async () => {
        if (++reads === 2) throw new Error('轴配置服务暂不可用')
        return {
          profiles: [
            { axis_count: 3, axes: 'XYZ', available: true, reason: '' },
            { axis_count: 4, axes: 'XYZC', available: true, reason: '' },
            { axis_count: 5, axes: 'XYZAC', available: true, reason: '' },
          ], configured_axis_count: 3, operation: null,
        }
      },
      request: async () => { throw new Error('不应提交配置') },
    }
  })
  await page.goto('/')
  await page.getByRole('button', { name: '控制', exact: true }).click()
  await page.getByRole('button', { name: '轴配置', exact: true }).click()
  const refresh = page.getByRole('button', { name: '刷新状态' })
  const save = page.getByRole('button', { name: '保存参数', exact: true })
  await expect(save).toBeEnabled()
  await refresh.click()
  await expect(page.getByRole('alert')).toHaveText('轴配置服务暂不可用')
  await expect(save).toBeDisabled()
  await refresh.click()
  await expect(save).toBeEnabled()
  await expect(page.getByRole('alert')).toHaveCount(0)
})
