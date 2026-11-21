import { test, expect } from '@playwright/test'
import applicationVersion from '../../../../versions/version.json'

test('first activation sets a password, later sudo changes use the existing password', async ({ page }) => {
  await page.addInitScript(() => {
    let required = true
    let enabled = false
    let credential = ''
    window.cncAdminSudo = {
      status: async () => enabled,
      needsSetup: async () => required,
      enroll: async (code, password) => {
        if (!required || code !== '1234-5678-9ABC-DEF0-1234-5678-9ABC-DEF0') throw new Error('Invalid code')
        required = false
        credential = password
        return enabled = true
      },
      setEnabled: async (target, password) => {
        if (required || password !== credential) throw new Error('Invalid password')
        return enabled = target
      },
    }
  })
  await page.goto('/')
  await page.getByRole('button', { name: '设置', exact: true }).click()
  const toggle = page.getByRole('switch', { name: 'cnc_admin sudo' })
  await toggle.click()
  await page.getByLabel('一次性开通码').fill('1234-5678-9ABC-DEF0-1234-5678-9ABC-DEF0')
  await page.getByLabel('设置新密码').fill('fixture-password')
  await page.getByLabel('确认新密码').fill('different')
  await page.getByRole('button', { name: '设置密码并开启' }).click()
  await expect(page.getByRole('alert')).toHaveText('两次输入的密码不一致')
  await page.getByLabel('确认新密码').fill('fixture-password')
  await page.getByRole('button', { name: '设置密码并开启' }).click()
  await expect(toggle).toBeChecked()
  await toggle.click()
  await expect(page.getByLabel('一次性开通码')).toHaveCount(0)
  await page.getByLabel('管理员密码').fill('fixture-password')
  await page.getByRole('button', { name: '确认', exact: true }).click()
  await expect(toggle).not.toBeChecked()
})

test('settings displays the configured application version below ArcnOS', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '设置', exact: true }).click()
  const title = page.getByRole('heading', { name: 'ArcnOS', exact: true })
  const version = page.getByLabel('系统版本', { exact: true })
  await expect(title).toBeVisible()
  await expect(version).toHaveText(applicationVersion.version)
  const titleBox = await title.boundingBox()
  const versionBox = await version.boundingBox()
  expect(versionBox!.y).toBeGreaterThanOrEqual(titleBox!.y + titleBox!.height)
  await expect(page.getByRole('article', { name: '系统信息', exact: true })).toHaveCount(1)
  for (const name of ['CPU', 'GPU', '内存', 'Linux 内核']) {
    const row = page.getByRole('group', { name, exact: true })
    await expect(row).toBeVisible()
    await expect(row.locator('dd')).toHaveText('-')
  }
  await expect(page.getByText(/浏览器预览无法读取|不可用|系统可用总容量/)).toHaveCount(0)
})

test('settings renders host snapshots and clears stale values after a failed automatic refresh', async ({ page }) => {
  await page.clock.install()
  await page.addInitScript(() => {
    let calls = 0
    window.cncSystem = { getInfo: async () => {
      if (++calls > 1) throw new Error('Test helper unavailable')
      return {
        schemaVersion: 1, cpu: { model: 'Fixture CPU', logicalCores: 8 },
        gpus: [{ model: 'Fixture GPU', vendorId: '1234', deviceId: '0001', driver: 'test-driver' }],
        memory: { totalBytes: 16 * 1024 ** 3, availableBytes: 0 }, kernel: '6.12-fixture',
      }
    } }
  })
  await page.goto('/')
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await expect(page.getByRole('group', { name: 'CPU', exact: true })).toContainText('Fixture CPU')
  await expect(page.getByRole('group', { name: 'GPU', exact: true })).toContainText('Fixture GPU')
  await expect(page.getByRole('group', { name: '内存', exact: true })).toContainText('16.0 GiB')
  await expect(page.getByRole('group', { name: 'Linux 内核', exact: true })).toContainText('6.12-fixture')
  await page.clock.fastForward(10000)
  await expect(page.getByRole('group', { name: 'CPU', exact: true }).locator('dd')).toHaveText('-')
  await expect(page.getByText('Test helper unavailable', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Fixture CPU', { exact: true })).toHaveCount(0)
})
